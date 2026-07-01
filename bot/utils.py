import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qsl

from config import config

STATUS_LABELS = {
    "awaiting_payment": "Ожидает оплаты",
    "paid": "Оплачено",
    "in_delivery": "В доставке",
    "awaiting_pickup": "Ожидает получения",
    "closed": "Закрыт",
    "canceled": "Отменен",
}

DELIVERY_LABELS = {
    "cdek": "CDEK",
    "yandex": "Яндекс Доставка",
    "pickup": "Самовывоз",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_price(value: int | float) -> str:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,}".replace(",", ".") + "₽"


def escape_html(text: object) -> str:
    value = "" if text is None else str(text)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def code(text: object) -> str:
    return f"<code>{escape_html(text)}</code>"


def slugify(value: str, max_len: int = 42) -> str:
    value = value.lower().strip()
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
        "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    value = "".join(translit.get(char, char) for char in value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if not value:
        value = "product"
    return value[:max_len].strip("-") or "product"


def make_product_id(brand: str, name: str) -> str:
    # Держим ID достаточно коротким, чтобы callback_data Telegram
    # не превышал лимит даже у кнопок удаления/редактирования.
    base = slugify(f"{brand}-{name}", max_len=36)
    return f"{base}-{uuid.uuid4().hex[:8]}"


def parse_price(text: str) -> int | None:
    normalized = re.sub(r"[^0-9]", "", text or "")
    if not normalized:
        return None
    return int(normalized)


def parse_size_stock(text: str) -> tuple[list[str], dict[str, int]]:
    """Parse sizes like: S:2, M:3, L:0 or 42-1, 43-2."""
    sizes: list[str] = []
    stock: dict[str, int] = {}
    chunks = [part.strip() for part in re.split(r"[,;\n]+", text or "") if part.strip()]
    for chunk in chunks:
        if ":" in chunk:
            size, qty = chunk.split(":", 1)
        elif "-" in chunk:
            size, qty = chunk.split("-", 1)
        else:
            size, qty = chunk, "1"
        size = size.strip().upper()
        qty_digits = re.sub(r"[^0-9]", "", qty)
        quantity = int(qty_digits) if qty_digits else 0
        if size:
            sizes.append(size)
            stock[size] = quantity
    return sizes, stock


def verify_telegram_init_data(init_data: str) -> dict:
    """Verify Telegram WebApp initData and return parsed user payload."""
    if not init_data:
        raise ValueError("Telegram initData отсутствует")
    if not config.bot_token:
        raise ValueError("BOT_TOKEN не указан")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise ValueError("В initData нет hash")

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=config.bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Некорректный Telegram initData")

    user_raw = pairs.get("user")
    if not user_raw:
        raise ValueError("В initData нет user")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Не удалось прочитать user из initData") from exc

    if not user.get("id"):
        raise ValueError("В initData нет user.id")

    return user


def get_product_image_url(product: dict) -> str:
    images = product.get("images") or []
    path = product.get("detailImage") or (images[0] if images else "")
    if not path:
        return ""
    if str(path).startswith("http"):
        return str(path)
    base = config.mini_app_url.rstrip("/")
    return f"{base}/{str(path).lstrip('/')}"


def build_pickup_text(items: list[dict], total_price: int) -> str:
    lines = ["Привет, хочу заказать:", ""]
    for index, item in enumerate(items, start=1):
        product = item.get("productSnapshot") or {}
        brand = item.get("brand") or product.get("brand") or ""
        name = item.get("name") or product.get("name") or ""
        size = item.get("size") or ""
        price = item.get("price") or product.get("price") or 0
        photo_url = get_product_image_url(product)
        lines.extend(
            [
                f"{index}. {brand} — {name}",
                f"Размер: {size}",
                f"Цена: {format_price(price)}",
            ]
        )
        if photo_url:
            lines.append(f"Фото: {photo_url}")
        lines.append("")
    lines.extend([f"Итого: {format_price(total_price)}", "Способ получения: Самовывоз"])
    return "\n".join(lines)


def product_short_title(product: dict) -> str:
    brand = product.get("brand") or ""
    name = product.get("name") or ""
    size_count = len(product.get("sizes") or [])
    active = "активен" if product.get("isActive", True) else "скрыт"
    if product.get("autoHiddenNoStock"):
        active = "нет остатков"
    base_price = parse_price(str(product.get("price") or "")) or 0
    discount_price = parse_price(str(product.get("discountPrice") or "")) or 0
    price_text = format_price(discount_price) if discount_price and discount_price < base_price else format_price(base_price)
    return f"{brand} — {name}\n{price_text} · {product.get('category', '')} · {size_count} разм. · {active}"
