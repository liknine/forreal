from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from config import CATEGORIES


def main_menu_kb(mini_app_url: str) -> ReplyKeyboardMarkup:
    # ВАЖНО: Telegram.WebApp.sendData корректно отправляет web_app_data в бота
    # именно когда Mini App открыт через KeyboardButton(web_app), а не через inline-кнопку.
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Открыть каталог", web_app=WebAppInfo(url=mini_app_url))]
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Откройте каталог ForReal",
    )


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Заявки", callback_data="admin:orders"),
                InlineKeyboardButton(text="Товары", callback_data="admin:products"),
            ],
            [InlineKeyboardButton(text="Добавить товар", callback_data="admin:add_product")],
            [
                InlineKeyboardButton(text="Реквизиты", callback_data="admin:payment"),
                InlineKeyboardButton(text="Фото главной", callback_data="admin:hero"),
            ],
            [InlineKeyboardButton(text="Синхронизировать GitHub", callback_data="admin:sync")],
        ]
    )


def product_categories_kb() -> InlineKeyboardMarkup:
    rows = []
    for category in CATEGORIES:
        rows.append([InlineKeyboardButton(text=category.label, callback_data=f"product:add:cat:{category.key}")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="product:add:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def accept_photos_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять фото", callback_data="product:add:finish")],
            [InlineKeyboardButton(text="Отмена", callback_data="product:add:cancel")],
        ]
    )


def product_search_prompt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Показать все товары", callback_data="product:search:all")],
            [InlineKeyboardButton(text="Назад", callback_data="admin:back")],
        ]
    )


def products_list_kb(
    products: list[dict],
    page: int = 0,
    page_size: int = 12,
    *,
    pagination_prefix: str = "product:list",
    search_mode: bool = False,
) -> InlineKeyboardMarkup:
    total = len(products)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    start = page * page_size
    end = start + page_size

    search_text = "🔎 Новый поиск" if search_mode else "🔎 Поиск товара"
    rows = [[InlineKeyboardButton(text=search_text, callback_data="product:search:start")]]
    for product in products[start:end]:
        active = "🟢" if product.get("isActive", True) else "⚫️"
        text = f"{active} {product.get('brand', '')} — {product.get('name', '')}"[:55]
        rows.append([InlineKeyboardButton(text=text, callback_data=f"product:view:{product.get('id')}")])

    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="‹", callback_data=f"{pagination_prefix}:{page - 1}"))
        current_callback = "product:search:noop" if search_mode else f"{pagination_prefix}:{page}"
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=current_callback))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="›", callback_data=f"{pagination_prefix}:{page + 1}"))
        rows.append(nav)

    if search_mode:
        rows.append([InlineKeyboardButton(text="Показать все товары", callback_data="product:search:all")])
    rows.append([InlineKeyboardButton(text="Добавить товар", callback_data="admin:add_product")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_manage_kb(product: dict) -> InlineKeyboardMarkup:
    product_id = product.get("id")
    is_active = product.get("isActive", True)
    visibility_text = "Скрыть" if is_active else "Показать"
    visibility_action = "hide" if is_active else "show"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Редактировать", callback_data=f"product:edit:{product_id}")],
            [InlineKeyboardButton(text=visibility_text, callback_data=f"product:{visibility_action}:{product_id}")],
            [InlineKeyboardButton(text="Удалить", callback_data=f"product:delete:{product_id}")],
            [InlineKeyboardButton(text="К товарам", callback_data="admin:products")],
        ]
    )


def product_edit_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Цена", callback_data="product:edit_field:price"),
                InlineKeyboardButton(text="Скидка", callback_data="product:edit_field:discount"),
            ],
            [InlineKeyboardButton(text="Остатки", callback_data="product:edit_field:sizes")],
            [
                InlineKeyboardButton(text="Бренд", callback_data="product:edit_field:brand"),
                InlineKeyboardButton(text="Название", callback_data="product:edit_field:name"),
            ],
            [
                InlineKeyboardButton(text="Категория", callback_data="product:edit_field:category"),
                InlineKeyboardButton(text="Описание", callback_data="product:edit_field:details"),
            ],
            [InlineKeyboardButton(text="Фото", callback_data="product:edit_field:photos")],
            [InlineKeyboardButton(text="Отмена", callback_data="product:edit_cancel")],
        ]
    )


def product_edit_categories_kb() -> InlineKeyboardMarkup:
    rows = []
    for category in CATEGORIES:
        rows.append([InlineKeyboardButton(text=category.label, callback_data=f"product:edit_cat:{category.key}")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="product:edit_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_edit_photos_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Заменить фото", callback_data="product:edit_photos_finish")],
            [InlineKeyboardButton(text="Отмена", callback_data="product:edit_cancel")],
        ]
    )


def client_payment_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ОТПРАВИТЬ ЧЕК", callback_data=f"receipt:start:{order_id}")]
        ]
    )


def admin_order_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"order:paid:{order_id}")],
            [
                InlineKeyboardButton(text="🚚 В доставке", callback_data=f"order:in_delivery:{order_id}"),
                InlineKeyboardButton(text="📦 Ожидает получения", callback_data=f"order:awaiting_pickup:{order_id}"),
            ],
            [
                InlineKeyboardButton(text="🏁 Закрыть", callback_data=f"order:closed:{order_id}"),
                InlineKeyboardButton(text="✖️ Отменить", callback_data=f"order:canceled:{order_id}"),
            ],
        ]
    )



def admin_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin:back")]]
    )


def home_hero_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заменить фото", callback_data="admin:hero_replace")],
            [InlineKeyboardButton(text="Удалить фото", callback_data="admin:hero_delete")],
            [InlineKeyboardButton(text="Назад", callback_data="admin:back")],
        ]
    )
