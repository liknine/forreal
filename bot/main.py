import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, Message

from config import CATEGORY_LABELS, config
from db import get_order, get_recent_orders, init_db, set_payment_proof, update_order_status
from github_storage import (
    add_or_update_product,
    decrease_stock,
    delete_product,
    find_product,
    get_payment_text_sync,
    load_products,
    load_settings,
    push_to_github,
    push_public_orders_to_github,
    save_home_hero_image,
    save_payment_text,
    save_product_photos,
    save_public_orders,
    save_user_avatar,
    remove_home_hero_image,
    toggle_product_active,
)
from keyboards import (
    accept_photos_kb,
    admin_cancel_kb,
    admin_order_kb,
    client_payment_kb,
    admin_panel_kb,
    home_hero_kb,
    main_menu_kb,
    product_categories_kb,
    product_edit_categories_kb,
    product_edit_kb,
    product_edit_photos_kb,
    product_manage_kb,
    product_search_prompt_kb,
    products_list_kb,
)
from order_messages import build_admin_order_text, build_client_payment_text
from order_service import OrderValidationError, create_order_from_payload
from utils import (
    STATUS_LABELS,
    code,
    escape_html,
    format_price,
    make_product_id,
    now_iso,
    parse_price,
    parse_size_stock,
    product_short_title,
)


class ReceiptState(StatesGroup):
    waiting_photo = State()


class AddProductState(StatesGroup):
    category = State()
    brand = State()
    name = State()
    price = State()
    sizes = State()
    details = State()
    photos = State()


class EditProductState(StatesGroup):
    value = State()
    photos = State()


class ProductSearchState(StatesGroup):
    query = State()
    results = State()


class AdminSettingsState(StatesGroup):
    payment_text = State()
    hero_photo = State()


dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


async def safe_send_admin_message(bot: Bot, admin_id: int, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id=admin_id, **kwargs)
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        print(f"ADMIN MESSAGE SKIPPED {admin_id}: {exc}")
        return False
    except Exception as exc:
        print(f"ADMIN MESSAGE FAILED {admin_id}: {exc}")
        return False


async def safe_send_admin_photo(bot: Bot, admin_id: int, photo_id: str, caption: str, reply_markup) -> bool:
    try:
        await bot.send_photo(
            chat_id=admin_id,
            photo=photo_id,
            caption=caption,
            reply_markup=reply_markup,
        )
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        print(f"ADMIN PHOTO SKIPPED {admin_id}: {exc}")
        return False
    except Exception as exc:
        print(f"ADMIN PHOTO FAILED {admin_id}: {exc}")
        return False


async def safe_send_admin_document(bot: Bot, admin_id: int, document_id: str, caption: str, reply_markup) -> bool:
    try:
        await bot.send_document(
            chat_id=admin_id,
            document=document_id,
            caption=caption,
            reply_markup=reply_markup,
        )
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        print(f"ADMIN DOCUMENT SKIPPED {admin_id}: {exc}")
        return False
    except Exception as exc:
        print(f"ADMIN DOCUMENT FAILED {admin_id}: {exc}")
        return False


async def require_admin_message(message: Message) -> bool:
    if not is_admin(message.from_user.id):
        await message.answer("У тебя нет доступа к админ-панели.")
        return False
    return True


async def require_admin_callback(callback: CallbackQuery) -> bool:
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return False
    return True


def append_url_params(url: str, params: dict[str, str]) -> str:
    clean_params = {key: value for key, value in params.items() if value not in (None, "")}
    if not clean_params:
        return url

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(clean_params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


async def build_personal_mini_app_url(message: Message) -> str:
    """Add reliable Telegram user data to the WebApp URL.

    Telegram WebApp initData can be missing on some cached/old buttons. These params are not used for
    order security; they are only a profile UI fallback.
    """
    user = message.from_user
    params = {
        "fr_uid": str(user.id),
        "fr_first": user.first_name or "",
        "fr_last": user.last_name or "",
        "fr_username": user.username or "",
    }

    avatar_url = await save_user_avatar(message.bot, user.id)
    if avatar_url:
        params["fr_photo"] = avatar_url

    print(
        "PROFILE BUTTON DATA",
        f"user_id={user.id}",
        f"username={user.username or '-'}",
        f"avatar={'ok' if avatar_url else 'missing'}",
    )
    return append_url_params(config.mini_app_url, params)


async def publish_public_orders(reason: str = "Update public orders") -> None:
    """Write safe order list to data/orders_public.json and autopush it to GitHub if token is set."""
    try:
        orders = await get_recent_orders(limit=500)
        await save_public_orders(orders)
        await push_public_orders_to_github(reason)
        print("PUBLIC ORDERS SYNCED", len(orders), reason)
    except Exception as exc:
        # Do not break customer/admin flow if GitHub sync fails.
        print("PUBLIC ORDERS SYNC FAILED", repr(exc))


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    mini_app_url = await build_personal_mini_app_url(message)
    await message.answer(
        "Привет. Это каталог ForReal.\n\nОткрой каталог через кнопку снизу — так заказ корректно отправится в бота.",
        reply_markup=main_menu_kb(mini_app_url),
    )


@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message) -> None:
    print("WEB_APP_DATA RECEIVED", message.from_user.id, (message.web_app_data.data or "")[:300])
    try:
        payload = json.loads(message.web_app_data.data or "{}")
    except json.JSONDecodeError:
        await message.answer("Не удалось прочитать данные заказа. Попробуйте оформить заказ еще раз.")
        return

    if payload.get("type") != "order":
        await message.answer("Получены неизвестные данные из Mini App.")
        return

    user = {
        "id": message.from_user.id,
        "username": message.from_user.username or "",
        "first_name": message.from_user.first_name or "",
    }

    try:
        order = await create_order_from_payload(payload, user)
    except OrderValidationError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer("Не удалось создать заказ. Попробуйте еще раз или свяжитесь с админом.")
        raise

    print("ORDER CREATED", order.get("orderNumber"), "admins", list(config.admin_ids))

    if order.get("_isDuplicate"):
        await publish_public_orders("Sync duplicate public order")
        await message.answer(
            "Этот заказ уже был создан. Повторно заявку админу не отправляю.\n\n"
            + build_client_payment_text(order),
            reply_markup=client_payment_kb(order["id"]),
        )
        return

    await publish_public_orders("Add public order")

    admin_text = build_admin_order_text(order)
    delivered_admins = 0
    for admin_id in config.admin_ids:
        if await safe_send_admin_message(
            message.bot,
            admin_id,
            text=admin_text,
            reply_markup=admin_order_kb(order["id"]),
        ):
            delivered_admins += 1

    if delivered_admins == 0:
        print("WARNING: ORDER WAS NOT DELIVERED TO ANY ADMIN", order.get("orderNumber"), list(config.admin_ids))

    await message.answer(
        build_client_payment_text(order),
        reply_markup=client_payment_kb(order["id"]),
    )


@dp.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Твой Telegram ID: {code(message.from_user.id)}")


@dp.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not await require_admin_message(message):
        return
    await message.answer("Админ-панель ForReal", reply_markup=admin_panel_kb())


@dp.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    if not await require_admin_message(message):
        return
    await send_recent_orders(message)


@dp.message(Command("products"))
async def cmd_products(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return
    await state.clear()
    await send_products_list(message)


@dp.callback_query(F.data.startswith("admin:"))
async def admin_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return

    action = callback.data.split(":", 1)[1]

    if action == "orders":
        await send_recent_orders(callback.message)
    elif action == "products":
        await state.clear()
        await send_products_list(callback.message)
    elif action == "add_product":
        await state.clear()
        await state.set_state(AddProductState.category)
        await callback.message.answer("Выбери категорию товара:", reply_markup=product_categories_kb())
    elif action == "payment":
        await state.clear()
        await state.set_state(AdminSettingsState.payment_text)
        current = get_payment_text_sync()
        await callback.message.answer(
            "Отправь новый текст реквизитов одним сообщением. Клиентам будет приходить ровно этот текст.\n\n"
            "Пример:\n"
            "Оплата на карту 0000 0000 0000 0000\n"
            "Получатель: Иван И.\n\n"
            f"Сейчас указано:\n{code(current)}",
            reply_markup=admin_cancel_kb(),
        )
    elif action == "hero":
        await state.clear()
        settings = await load_settings()
        current = settings.get("homeHeroImage") or "стандартная assets/home-hero.png"
        await callback.message.answer(
            "Фото главной страницы.\n\n"
            f"Сейчас: {code(current)}\n\n"
            "Для замены нажми кнопку и отправь фото. Для удаления — вернем стандартную фотку.",
            reply_markup=home_hero_kb(),
        )
    elif action == "hero_replace":
        await state.clear()
        await state.set_state(AdminSettingsState.hero_photo)
        await callback.message.answer(
            "Отправь новую фотку для главной страницы.\n\n"
            "Размер: 1200×900 px или 1600×1200 px.\n"
            "Формат: JPG или PNG.",
            reply_markup=admin_cancel_kb(),
        )
    elif action == "hero_delete":
        await state.clear()
        try:
            await remove_home_hero_image()
            await callback.message.answer(
                "Кастомная фотка главной удалена из настроек. Теперь будет стандартная assets/home-hero.png.",
                reply_markup=admin_panel_kb(),
            )
        except Exception as exc:
            await callback.message.answer(f"Не удалось удалить фото главной: {escape_html(exc)}")
    elif action == "sync":
        try:
            await push_to_github()
            await publish_public_orders("Manual sync public orders")
            await callback.message.answer("Синхронизация GitHub выполнена.")
        except Exception as exc:
            await callback.message.answer(f"Не удалось синхронизировать GitHub: {escape_html(exc)}")
    elif action == "back":
        await state.clear()
        await callback.message.answer("Админ-панель ForReal", reply_markup=admin_panel_kb())

    await callback.answer()


@dp.message(AdminSettingsState.payment_text)
async def admin_set_payment_text(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Текст реквизитов слишком короткий. Отправь реквизиты одним сообщением.")
        return
    try:
        await save_payment_text(text)
    except Exception as exc:
        await message.answer(f"Не удалось сохранить реквизиты: {escape_html(exc)}")
        return
    await state.clear()
    await message.answer("Реквизиты обновлены. Теперь клиентам будет приходить новый текст оплаты.", reply_markup=admin_panel_kb())


@dp.message(AdminSettingsState.hero_photo, F.photo | F.document)
async def admin_set_home_hero_photo(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return

    file_id = ""
    ext = ".jpg"
    if message.photo:
        file_id = message.photo[-1].file_id
        ext = ".jpg"
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        file_id = message.document.file_id
        filename = message.document.file_name or "home-hero.jpg"
        ext = Path(filename).suffix or ".jpg"

    if not file_id:
        await message.answer(
            "Нужно отправить фото или image-файл.\n\n"
            "Размер: 1200×900 px или 1600×1200 px.\n"
            "Формат: JPG или PNG.",
            reply_markup=admin_cancel_kb(),
        )
        return

    await message.answer("Сохраняю фото главной и синхронизирую GitHub...")
    try:
        settings = await save_home_hero_image(message.bot, file_id, ext)
    except Exception as exc:
        await message.answer(f"Не удалось сохранить фото главной: {escape_html(exc)}")
        return

    await state.clear()
    await message.answer(
        "Фото главной обновлено.\n\n"
        f"Файл: {code(settings.get('homeHeroImage') or 'стандартная фотка')}",
        reply_markup=admin_panel_kb(),
    )


@dp.message(AdminSettingsState.hero_photo)
async def admin_set_home_hero_photo_wrong(message: Message) -> None:
    await message.answer(
        "Отправь фото или image-файл.\n\n"
        "Размер: 1200×900 px или 1600×1200 px.\n"
        "Формат: JPG или PNG.",
        reply_markup=admin_cancel_kb(),
    )


async def send_recent_orders(message: Message) -> None:
    orders = await get_recent_orders(limit=10)
    if not orders:
        await message.answer("Заявок пока нет.")
        return
    for order in orders:
        await message.answer(build_order_short_text(order), reply_markup=admin_order_kb(order["id"]))


PRODUCTS_PAGE_SIZE = 12


def sorted_products(products: list[dict]) -> list[dict]:
    return sorted(products, key=lambda item: item.get("createdAt", ""), reverse=True)


def normalize_product_search_text(value: object) -> str:
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


def filter_products_by_query(products: list[dict], query: str) -> list[dict]:
    terms = normalize_product_search_text(query).split()
    if not terms:
        return []

    matches = []
    for product in products:
        searchable = normalize_product_search_text(
            f"{product.get('brand', '')} {product.get('name', '')}"
        )
        if all(term in searchable for term in terms):
            matches.append(product)
    return matches


def build_product_search_text(query: str, count: int) -> str:
    if count:
        return f"Поиск товаров: {code(query)}\nНайдено: {count}"
    return f"Поиск товаров: {code(query)}\n\nНичего не найдено."


async def load_sorted_products() -> list[dict]:
    return sorted_products(await load_products())


async def load_product_search_results(query: str) -> list[dict]:
    return filter_products_by_query(await load_sorted_products(), query)


async def send_products_list(message: Message, page: int = 0) -> None:
    products = await load_sorted_products()
    if not products:
        await message.answer("Товаров пока нет.", reply_markup=admin_panel_kb())
        return
    await message.answer(
        f"Товары ForReal: {len(products)}",
        reply_markup=products_list_kb(products, page=page, page_size=PRODUCTS_PAGE_SIZE),
    )


@dp.callback_query(F.data.startswith("product:list:"))
async def products_list_page_callback(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    try:
        page = int(callback.data.rsplit(":", 1)[1])
    except (TypeError, ValueError):
        page = 0

    products = await load_sorted_products()
    if not products:
        await callback.message.edit_text("Товаров пока нет.", reply_markup=admin_panel_kb())
        await callback.answer()
        return

    page_size = PRODUCTS_PAGE_SIZE
    pages = max(1, (len(products) + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    await callback.message.edit_text(
        f"Товары ForReal: {len(products)}",
        reply_markup=products_list_kb(products, page=page, page_size=page_size),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("product:search:"))
async def product_search_actions(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return

    action = callback.data.split(":", 2)[2]
    if action == "noop":
        await callback.answer()
        return

    if action == "start":
        await state.clear()
        await state.set_state(ProductSearchState.query)
        await callback.message.answer(
            "Введи бренд или название товара одним сообщением.\n\n"
            "Например:\n"
            "LANVIN\n"
            "BLACK LOGO TEE\n"
            "LANVIN BLACK",
            reply_markup=product_search_prompt_kb(),
        )
        await callback.answer()
        return

    if action == "all":
        await state.clear()
        await send_products_list(callback.message)
        await callback.answer()
        return

    await callback.answer("Неизвестное действие", show_alert=True)


@dp.message(ProductSearchState.query)
async def product_search_query(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return

    query = " ".join((message.text or "").split())
    if not query:
        await message.answer(
            "Отправь название или бренд текстом.",
            reply_markup=product_search_prompt_kb(),
        )
        return
    if len(query) > 100:
        await message.answer(
            "Запрос слишком длинный. Введи бренд или название короче 100 символов.",
            reply_markup=product_search_prompt_kb(),
        )
        return

    products = await load_product_search_results(query)
    await state.update_data(product_search_query=query, product_search_page=0)
    await state.set_state(ProductSearchState.results)
    await message.answer(
        build_product_search_text(query, len(products)),
        reply_markup=products_list_kb(
            products,
            page=0,
            page_size=PRODUCTS_PAGE_SIZE,
            pagination_prefix="product:search_page",
            search_mode=True,
        ),
    )


@dp.callback_query(F.data.startswith("product:search_page:"))
async def product_search_page(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return

    data = await state.get_data()
    query = str(data.get("product_search_query") or "").strip()
    if not query:
        await state.clear()
        await callback.answer("Поиск устарел. Начни заново.", show_alert=True)
        await send_products_list(callback.message)
        return

    try:
        page = int(callback.data.rsplit(":", 1)[1])
    except (TypeError, ValueError):
        page = 0

    products = await load_product_search_results(query)
    pages = max(1, (len(products) + PRODUCTS_PAGE_SIZE - 1) // PRODUCTS_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    await state.update_data(product_search_page=page)
    await callback.message.edit_text(
        build_product_search_text(query, len(products)),
        reply_markup=products_list_kb(
            products,
            page=page,
            page_size=PRODUCTS_PAGE_SIZE,
            pagination_prefix="product:search_page",
            search_mode=True,
        ),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("product:add:"))
async def add_product_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return

    action = callback.data.split(":", 2)[2]

    if action == "cancel":
        await state.clear()
        await callback.message.answer("Добавление товара отменено.", reply_markup=admin_panel_kb())
        await callback.answer()
        return

    if action.startswith("cat:"):
        category_key = action.split(":", 1)[1]
        category_label = CATEGORY_LABELS.get(category_key)
        if not category_label:
            await callback.answer("Неизвестная категория", show_alert=True)
            return
        await state.update_data(category=category_label)
        await state.set_state(AddProductState.brand)
        await callback.message.answer("Введи бренд товара. Например: MIHARA YASUHIRO")
        await callback.answer()
        return

    if action == "finish":
        data = await state.get_data()
        photos = data.get("photos") or []
        if not photos:
            await callback.answer("Добавь хотя бы одно фото", show_alert=True)
            return
        await finish_add_product(callback, state, photos)
        await callback.answer()
        return


@dp.message(AddProductState.brand)
async def add_product_brand(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return
    brand = (message.text or "").strip()
    if len(brand) < 2:
        await message.answer("Бренд слишком короткий. Введи бренд еще раз.")
        return
    await state.update_data(brand=brand)
    await state.set_state(AddProductState.name)
    await message.answer("Введи название товара. Например: BLACK LOGO TEE")


@dp.message(AddProductState.name)
async def add_product_name(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое. Введи название еще раз.")
        return
    await state.update_data(name=name)
    await state.set_state(AddProductState.price)
    await message.answer("Введи цену в рублях. Например: 12500")


@dp.message(AddProductState.price)
async def add_product_price(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return
    price = parse_price(message.text or "")
    if not price or price <= 0:
        await message.answer("Не понял цену. Введи числом, например: 12500")
        return
    await state.update_data(price=price)
    await state.set_state(AddProductState.sizes)
    await message.answer(
        "Введи размеры и остатки.\n\n"
        "Пример:\n"
        "S:2, M:3, L:1, XL:0\n\n"
        "Для обуви можно так:\n"
        "42:1, 43:2, 44:0"
    )


@dp.message(AddProductState.sizes)
async def add_product_sizes(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return
    sizes, size_stock = parse_size_stock(message.text or "")
    if not sizes:
        await message.answer("Не понял размеры. Напиши по примеру: S:2, M:3, L:1")
        return
    await state.update_data(sizes=sizes, sizeStock=size_stock)
    await state.set_state(AddProductState.details)
    await message.answer("Введи детали / описание товара. Можно одним сообщением.")


@dp.message(AddProductState.details)
async def add_product_details(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return
    details = (message.text or "").strip()
    await state.update_data(details=details)
    await state.set_state(AddProductState.photos)
    await message.answer(
        "Теперь отправь фото товара. Можно несколько сообщений.\n\n"
        "Когда все фото отправлены, нажми ✅ Принять фото.",
        reply_markup=accept_photos_kb(),
    )


@dp.message(AddProductState.photos, F.photo | F.document)
async def add_product_photo(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return

    photo_data = None
    if message.photo:
        photo_data = {"file_id": message.photo[-1].file_id, "ext": ".jpg"}
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        filename = message.document.file_name or "image.jpg"
        ext = Path(filename).suffix or ".jpg"
        photo_data = {"file_id": message.document.file_id, "ext": ext}

    if not photo_data:
        await message.answer("Нужно отправить фото или image-документ.", reply_markup=accept_photos_kb())
        return

    data = await state.get_data()
    photos = data.get("photos") or []
    photos.append(photo_data)
    await state.update_data(photos=photos)
    await message.answer(f"Фото добавлено: {len(photos)} шт.", reply_markup=accept_photos_kb())


@dp.message(AddProductState.photos)
async def add_product_photo_wrong(message: Message) -> None:
    await message.answer("Отправь фото товара или нажми ✅ Принять фото.", reply_markup=accept_photos_kb())


async def finish_add_product(callback: CallbackQuery, state: FSMContext, photos: list[dict]) -> None:
    data = await state.get_data()
    brand = data["brand"]
    name = data["name"]
    product_id = make_product_id(brand, name)

    await callback.message.answer("Сохраняю товар и фото...")
    image_paths = await save_product_photos(callback.bot, product_id, photos)

    product = {
        "id": product_id,
        "brand": brand,
        "name": name,
        "price": data["price"],
        "currency": "RUB",
        "category": data["category"],
        "sizes": data["sizes"],
        "sizeStock": data["sizeStock"],
        "details": data.get("details") or "",
        "images": image_paths,
        "detailImage": image_paths[0] if image_paths else "",
        "isActive": True,
        "createdAt": now_iso(),
    }

    try:
        await add_or_update_product(product)
        await state.clear()
        await callback.message.answer(
            "Товар добавлен.\n\n" + build_product_text(product),
            reply_markup=product_manage_kb(product),
        )
    except Exception as exc:
        await callback.message.answer(
            "Товар локально собран, но возникла ошибка при сохранении/синхронизации:\n"
            f"{escape_html(exc)}"
        )


@dp.callback_query(F.data.startswith("product:view:"))
async def product_view(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return
    product_id = callback.data.split(":", 2)[2]
    product = await find_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await callback.message.answer(build_product_text(product), reply_markup=product_manage_kb(product))
    await callback.answer()




EDIT_FIELD_LABELS = {
    "brand": "бренд",
    "name": "название",
    "price": "цену",
    "discount": "скидку",
    "sizes": "размеры/остатки",
    "details": "описание",
    "category": "категорию",
    "photos": "фото",
}


async def apply_product_updates(product_id: str, updates: dict, remove_keys: list[str] | None = None) -> dict | None:
    product = await find_product(product_id)
    if not product:
        return None
    updated = dict(product)
    for key in remove_keys or []:
        updated.pop(key, None)
    updated.update(updates)
    updated["id"] = product_id  # ID не меняем даже при смене бренда/названия.
    return await add_or_update_product(updated)


@dp.callback_query(F.data.startswith("product:edit:"))
async def product_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return
    product_id = callback.data.split(":", 2)[2]
    product = await find_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await state.clear()
    await state.update_data(edit_product_id=product_id)
    await callback.message.answer(
        "Что редактируем?\n\n"
        "ID товара не будет меняться, даже если изменить бренд или название.\n\n"
        + build_product_text(product),
        reply_markup=product_edit_kb(),
    )
    await callback.answer()


@dp.callback_query(F.data == "product:edit_cancel")
async def product_edit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return
    data = await state.get_data()
    product_id = data.get("edit_product_id")
    await state.clear()
    product = await find_product(product_id) if product_id else None
    if product:
        await callback.message.answer("Редактирование отменено.\n\n" + build_product_text(product), reply_markup=product_manage_kb(product))
    else:
        await callback.message.answer("Редактирование отменено.", reply_markup=admin_panel_kb())
    await callback.answer("Отменено")


@dp.callback_query(F.data.startswith("product:edit_field:"))
async def product_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return
    field = callback.data.split(":", 2)[2]
    data = await state.get_data()
    product_id = data.get("edit_product_id")
    product = await find_product(product_id) if product_id else None
    if not product:
        await state.clear()
        await callback.answer("Сначала открой товар заново", show_alert=True)
        return

    if field == "category":
        await callback.message.answer("Выбери новую категорию:", reply_markup=product_edit_categories_kb())
        await callback.answer()
        return

    if field == "photos":
        await state.set_state(EditProductState.photos)
        await state.update_data(edit_field="photos", edit_photos=[])
        await callback.message.answer(
            "Отправь новые фото товара. Можно несколькими сообщениями.\n\n"
            "Старые файлы не удаляются, чтобы не ломать старые заказы. "
            "После загрузки нажми ✅ Заменить фото.",
            reply_markup=product_edit_photos_kb(),
        )
        await callback.answer()
        return

    if field not in {"brand", "name", "price", "discount", "sizes", "details"}:
        await callback.answer("Неизвестное поле", show_alert=True)
        return

    await state.set_state(EditProductState.value)
    await state.update_data(edit_field=field)

    prompts = {
        "brand": "Введи новый бренд товара. ID останется прежним.",
        "name": "Введи новое название товара. ID останется прежним.",
        "price": "Введи новую обычную цену числом. Например: 12500",
        "discount": "Введи новую цену со скидкой. Она должна быть меньше обычной цены.\n\nНапример: 9900\n\nЧтобы убрать скидку, отправь: -",
        "sizes": "Введи новые размеры и остатки.\n\nПример: S:2, M:3, L:1, XL:0",
        "details": "Введи новое описание товара. Напиши '-' если описание нужно очистить.",
    }
    await callback.message.answer(prompts[field])
    await callback.answer()


@dp.callback_query(F.data.startswith("product:edit_cat:"))
async def product_edit_category(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return
    category_key = callback.data.split(":", 2)[2]
    category_label = CATEGORY_LABELS.get(category_key)
    if not category_label:
        await callback.answer("Неизвестная категория", show_alert=True)
        return

    data = await state.get_data()
    product_id = data.get("edit_product_id")
    product = await apply_product_updates(product_id, {"category": category_label}) if product_id else None
    if not product:
        await state.clear()
        await callback.answer("Товар не найден", show_alert=True)
        return

    await state.clear()
    await callback.message.answer("Категория обновлена.\n\n" + build_product_text(product), reply_markup=product_manage_kb(product))
    await callback.answer("Готово")


@dp.message(EditProductState.value)
async def product_edit_value(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return

    data = await state.get_data()
    product_id = data.get("edit_product_id")
    field = data.get("edit_field")
    text = (message.text or "").strip()

    if not product_id or field not in {"brand", "name", "price", "discount", "sizes", "details"}:
        await state.clear()
        await message.answer("Редактирование сброшено. Открой товар заново через /products.")
        return

    current_product = await find_product(product_id)
    if not current_product:
        await state.clear()
        await message.answer("Товар не найден. Открой список товаров заново через /products.")
        return

    updates = {}
    remove_keys: list[str] = []
    if field == "brand":
        if len(text) < 2:
            await message.answer("Бренд слишком короткий. Введи бренд еще раз.")
            return
        updates["brand"] = text
    elif field == "name":
        if len(text) < 2:
            await message.answer("Название слишком короткое. Введи название еще раз.")
            return
        updates["name"] = text
    elif field == "price":
        price = parse_price(text)
        if not price or price <= 0:
            await message.answer("Не понял цену. Введи числом, например: 12500")
            return
        updates["price"] = price
        old_discount = parse_price(str(current_product.get("discountPrice") or ""))
        if old_discount and old_discount >= price:
            remove_keys.append("discountPrice")
    elif field == "discount":
        if text in {"-", "—", "нет", "Нет", "НЕТ", "убрать", "Убрать"}:
            remove_keys.append("discountPrice")
        else:
            discount_price = parse_price(text)
            base_price = parse_price(str(current_product.get("price") or "")) or 0
            if not discount_price or discount_price <= 0:
                await message.answer("Не понял цену скидки. Введи числом, например: 9900, или '-' чтобы убрать скидку.")
                return
            if base_price <= 0 or discount_price >= base_price:
                await message.answer(
                    f"Цена со скидкой должна быть меньше обычной цены товара ({format_price(base_price)}).\n"
                    "Введи цену со скидкой еще раз или '-' чтобы убрать скидку."
                )
                return
            updates["discountPrice"] = discount_price
    elif field == "sizes":
        sizes, size_stock = parse_size_stock(text)
        if not sizes:
            await message.answer("Не понял размеры. Напиши по примеру: S:2, M:3, L:1")
            return
        updates["sizes"] = sizes
        updates["sizeStock"] = size_stock
    elif field == "details":
        updates["details"] = "" if text in {"-", "—", "нет", "Нет", "НЕТ"} else text

    try:
        product = await apply_product_updates(product_id, updates, remove_keys=remove_keys)
    except Exception as exc:
        await message.answer(f"Не удалось обновить товар: {escape_html(exc)}")
        return

    if not product:
        await state.clear()
        await message.answer("Товар не найден. Открой список товаров заново через /products.")
        return

    await state.clear()
    await message.answer(
        f"Обновлено: {EDIT_FIELD_LABELS.get(field, field)}.\n\n" + build_product_text(product),
        reply_markup=product_manage_kb(product),
    )


@dp.message(EditProductState.photos, F.photo | F.document)
async def product_edit_photo(message: Message, state: FSMContext) -> None:
    if not await require_admin_message(message):
        return

    photo_data = None
    if message.photo:
        photo_data = {"file_id": message.photo[-1].file_id, "ext": ".jpg"}
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        filename = message.document.file_name or "image.jpg"
        ext = Path(filename).suffix or ".jpg"
        photo_data = {"file_id": message.document.file_id, "ext": ext}

    if not photo_data:
        await message.answer("Нужно отправить фото или image-документ.", reply_markup=product_edit_photos_kb())
        return

    data = await state.get_data()
    photos = data.get("edit_photos") or []
    photos.append(photo_data)
    await state.update_data(edit_photos=photos)
    await message.answer(f"Новое фото добавлено: {len(photos)} шт.", reply_markup=product_edit_photos_kb())


@dp.message(EditProductState.photos)
async def product_edit_photo_wrong(message: Message) -> None:
    await message.answer("Отправь новое фото товара или нажми ✅ Заменить фото.", reply_markup=product_edit_photos_kb())


@dp.callback_query(F.data == "product:edit_photos_finish")
async def product_edit_photos_finish(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return

    data = await state.get_data()
    product_id = data.get("edit_product_id")
    photos = data.get("edit_photos") or []
    if not product_id:
        await state.clear()
        await callback.answer("Открой товар заново", show_alert=True)
        return
    if not photos:
        await callback.answer("Добавь хотя бы одно фото", show_alert=True)
        return

    current_product = await find_product(product_id)
    if not current_product:
        await state.clear()
        await callback.answer("Товар не найден", show_alert=True)
        return

    await callback.message.answer("Сохраняю новые фото...")
    try:
        photo_key = f"{product_id}-{uuid4().hex[:8]}"
        image_paths = await save_product_photos(callback.bot, photo_key, photos)
        product = await apply_product_updates(
            product_id,
            {
                "images": image_paths,
                "detailImage": image_paths[0] if image_paths else "",
            },
        )
    except Exception as exc:
        await callback.message.answer(f"Не удалось заменить фото: {escape_html(exc)}")
        return

    if not product:
        await state.clear()
        await callback.answer("Товар не найден", show_alert=True)
        return

    await state.clear()
    await callback.message.answer("Фото товара заменены.\n\n" + build_product_text(product), reply_markup=product_manage_kb(product))
    await callback.answer("Готово")


@dp.callback_query(F.data.startswith("product:hide:") | F.data.startswith("product:show:"))
async def product_toggle(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return
    _, action, product_id = callback.data.split(":", 2)
    is_active = action == "show"
    product = await toggle_product_active(product_id, is_active)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await callback.message.answer(build_product_text(product), reply_markup=product_manage_kb(product))
    await callback.answer("Готово")


@dp.callback_query(F.data.startswith("product:delete:"))
async def product_delete(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return
    product_id = callback.data.split(":", 2)[2]
    ok = await delete_product(product_id)
    if not ok:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await callback.message.answer("Товар удален из products.json.")
    await callback.answer("Удалено")


@dp.callback_query(F.data.startswith("receipt:start:"))
async def start_receipt(callback: CallbackQuery, state: FSMContext) -> None:
    order_id = callback.data.split(":", 2)[2]
    order = await get_order(order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if order["telegramId"] != callback.from_user.id:
        await callback.answer("Это не твой заказ", show_alert=True)
        return
    if order["status"] == "canceled":
        await callback.answer("Заказ отменен", show_alert=True)
        return

    await state.set_state(ReceiptState.waiting_photo)
    await state.update_data(order_id=order_id)
    await callback.message.answer("Отправьте фото перевода одним сообщением.")
    await callback.answer()


@dp.message(ReceiptState.waiting_photo, F.photo | F.document)
async def receive_receipt_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    order = await get_order(order_id)

    if not order or order["telegramId"] != message.from_user.id:
        await state.clear()
        await message.answer("Не удалось найти заказ для этого чека.")
        return

    photo_id = None
    proof_kind = "photo"
    if message.photo:
        photo_id = message.photo[-1].file_id
        proof_kind = "photo"
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
        photo_id = message.document.file_id
        proof_kind = "document"

    if not photo_id:
        await message.answer("Нужно отправить именно фото перевода.")
        return

    order = await set_payment_proof(order_id, photo_id)
    await state.clear()

    await message.answer("Фото оплаты принято. Ожидайте обработки заявки.")

    caption = (
        f"Фото оплаты по заказу #{order['orderNumber']}\n\n"
        f"Клиент: @{escape_html(order.get('username') or 'без username')}\n"
        f"Telegram ID: {code(order['telegramId'])}\n"
        f"Сумма: {code(format_price(order['totalPrice']))}\n"
        f"Статус: {code(STATUS_LABELS.get(order['status'], order['status']))}"
    )

    delivered_admins = 0
    for admin_id in config.admin_ids:
        if proof_kind == "document":
            ok = await safe_send_admin_document(
                message.bot,
                admin_id,
                photo_id,
                caption,
                admin_order_kb(order_id),
            )
        else:
            ok = await safe_send_admin_photo(
                message.bot,
                admin_id,
                photo_id,
                caption,
                admin_order_kb(order_id),
            )
        if ok:
            delivered_admins += 1

    if delivered_admins == 0:
        print("WARNING: PAYMENT PROOF WAS NOT DELIVERED TO ANY ADMIN", order.get("orderNumber"), list(config.admin_ids))


@dp.message(ReceiptState.waiting_photo)
async def receive_receipt_wrong(message: Message) -> None:
    await message.answer("Отправьте фото перевода. Текстом чек принять нельзя.")


@dp.callback_query(F.data.startswith("order:"))
async def order_status_callback(callback: CallbackQuery) -> None:
    if not await require_admin_callback(callback):
        return

    _, new_status, order_id = callback.data.split(":", 2)
    allowed = {"paid", "in_delivery", "awaiting_pickup", "closed", "canceled"}
    if new_status not in allowed:
        await callback.answer("Неизвестный статус", show_alert=True)
        return

    before = await get_order(order_id)
    if not before:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    stock_warning = ""
    if new_status == "paid" and before["status"] != "paid":
        try:
            await decrease_stock(before["items"])
        except Exception as exc:
            stock_warning = (
                "\n\n⚠️ Статус изменен, но синхронизация остатков с GitHub не прошла. "
                f"Проверь GITHUB_TOKEN и нажми Синхронизировать GitHub. Ошибка: {escape_html(exc)}"
            )

    order = await update_order_status(order_id, new_status)
    await publish_public_orders(f"Update order #{order['orderNumber']} status")
    label = STATUS_LABELS.get(new_status, new_status)

    await callback.message.answer(
        f"Статус заказа #{order['orderNumber']} изменен на {code(label)}." + stock_warning
    )

    try:
        await callback.bot.send_message(
            chat_id=order["telegramId"],
            text=f"Статус заказа #{order['orderNumber']} обновлен: {code(label)}.",
        )
    except Exception:
        pass

    await callback.answer("Статус обновлен")


def build_product_text(product: dict) -> str:
    stock = product.get("sizeStock") or {}
    stock_line = ", ".join(f"{size}: {qty}" for size, qty in stock.items()) or "—"
    status = "Активен" if product.get("isActive", True) else "Скрыт"
    if product.get("autoHiddenNoStock"):
        status = "Скрыт — нет остатков"
    images = product.get("images") or []
    base_price = parse_price(str(product.get("price") or "")) or 0
    discount_price = parse_price(str(product.get("discountPrice") or "")) or 0
    if discount_price and base_price and discount_price < base_price:
        price_line = f"{format_price(discount_price)} / старая {format_price(base_price)}"
    else:
        price_line = format_price(base_price)
    return (
        f"{product_short_title(product)}\n\n"
        f"ID: {code(product.get('id'))}\n"
        f"Бренд: {code(product.get('brand'))}\n"
        f"Название: {code(product.get('name'))}\n"
        f"Категория: {code(product.get('category'))}\n"
        f"Цена: {code(price_line)}\n"
        f"Остатки: {code(stock_line)}\n"
        f"Фото: {code(len(images))} шт.\n"
        f"Статус: {code(status)}"
    )


def build_order_short_text(order: dict) -> str:
    label = STATUS_LABELS.get(order.get("status"), order.get("status"))
    lines = [
        f"Заказ #{order['orderNumber']}",
        f"Клиент: @{escape_html(order.get('username') or 'без username')}",
        "",
        "Товары:",
    ]

    items = order.get("items") or []
    if items:
        for index, item in enumerate(items, start=1):
            snapshot = item.get("productSnapshot") or {}
            brand = item.get("brand") or snapshot.get("brand") or "—"
            name = item.get("name") or snapshot.get("name") or "—"
            size = item.get("size") or "—"
            quantity = int(item.get("quantity") or 1)
            price = int(item.get("price") or 0)
            lines.extend(
                [
                    f"{index}. {code(brand)} — {code(name)}",
                    f"   Размер: {code(size)} · Кол-во: {code(quantity)} · Цена: {code(format_price(price))}",
                ]
            )
    else:
        lines.append("—")

    lines.extend(
        [
            "",
            f"Сумма: {code(format_price(order['totalPrice']))}",
            f"Статус: {code(label)}",
        ]
    )
    return "\n".join(lines)


async def main() -> None:
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN не указан в bot/.env")

    await init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="id", description="Узнать Telegram ID"),
            BotCommand(command="admin", description="Админ-панель"),
            BotCommand(command="orders", description="Заявки"),
            BotCommand(command="products", description="Товары"),
        ]
    )

    print("ForReal bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
