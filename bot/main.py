import asyncio
import json
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
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
    load_products,
    push_to_github,
    save_product_photos,
    toggle_product_active,
)
from keyboards import (
    accept_photos_kb,
    admin_order_kb,
    client_payment_kb,
    admin_panel_kb,
    main_menu_kb,
    product_categories_kb,
    product_manage_kb,
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


dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


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


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет. Это каталог ForReal.",
        reply_markup=main_menu_kb(config.mini_app_url),
    )




@dp.message(F.web_app_data)
async def handle_web_app_data(message: Message) -> None:
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

    if order.get("_isDuplicate"):
        await message.answer(
            "Этот заказ уже был создан. Повторно заявку админу не отправляю.\n\n"
            + build_client_payment_text(order),
            reply_markup=client_payment_kb(order["id"]),
        )
        return

    admin_text = build_admin_order_text(order)
    for admin_id in config.admin_ids:
        await message.bot.send_message(
            chat_id=admin_id,
            text=admin_text,
            reply_markup=admin_order_kb(order["id"]),
        )

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
async def cmd_products(message: Message) -> None:
    if not await require_admin_message(message):
        return
    await send_products_list(message)


@dp.callback_query(F.data.startswith("admin:"))
async def admin_callbacks(callback: CallbackQuery, state: FSMContext) -> None:
    if not await require_admin_callback(callback):
        return

    action = callback.data.split(":", 1)[1]

    if action == "orders":
        await send_recent_orders(callback.message)
    elif action == "products":
        await send_products_list(callback.message)
    elif action == "add_product":
        await state.clear()
        await state.set_state(AddProductState.category)
        await callback.message.answer("Выбери категорию товара:", reply_markup=product_categories_kb())
    elif action == "sync":
        try:
            await push_to_github()
            await callback.message.answer("Синхронизация GitHub выполнена.")
        except Exception as exc:
            await callback.message.answer(f"Не удалось синхронизировать GitHub: {escape_html(exc)}")
    elif action == "back":
        await callback.message.answer("Админ-панель ForReal", reply_markup=admin_panel_kb())

    await callback.answer()


async def send_recent_orders(message: Message) -> None:
    orders = await get_recent_orders(limit=10)
    if not orders:
        await message.answer("Заявок пока нет.")
        return
    for order in orders:
        await message.answer(build_order_short_text(order), reply_markup=admin_order_kb(order["id"]))


async def send_products_list(message: Message) -> None:
    products = await load_products()
    products = sorted(products, key=lambda item: item.get("createdAt", ""), reverse=True)
    if not products:
        await message.answer("Товаров пока нет.", reply_markup=admin_panel_kb())
        return
    await message.answer("Товары ForReal:", reply_markup=products_list_kb(products))


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

    for admin_id in config.admin_ids:
        if proof_kind == "document":
            await message.bot.send_document(
                chat_id=admin_id,
                document=photo_id,
                caption=caption,
                reply_markup=admin_order_kb(order_id),
            )
        else:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=photo_id,
                caption=caption,
                reply_markup=admin_order_kb(order_id),
            )


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
    images = product.get("images") or []
    return (
        f"{product_short_title(product)}\n\n"
        f"ID: {code(product.get('id'))}\n"
        f"Бренд: {code(product.get('brand'))}\n"
        f"Название: {code(product.get('name'))}\n"
        f"Категория: {code(product.get('category'))}\n"
        f"Цена: {code(format_price(product.get('price', 0)))}\n"
        f"Остатки: {code(stock_line)}\n"
        f"Фото: {code(len(images))} шт.\n"
        f"Статус: {code(status)}"
    )


def build_order_short_text(order: dict) -> str:
    label = STATUS_LABELS.get(order.get("status"), order.get("status"))
    return (
        f"Заказ #{order['orderNumber']}\n"
        f"Клиент: @{escape_html(order.get('username') or 'без username')}\n"
        f"Сумма: {code(format_price(order['totalPrice']))}\n"
        f"Статус: {code(label)}"
    )


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
