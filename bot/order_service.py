import uuid
from typing import Any

from db import create_order
from github_storage import load_products


class OrderValidationError(ValueError):
    pass


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def create_order_from_payload(payload: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    items_in = payload.get("items") or []
    if not isinstance(items_in, list) or not items_in:
        raise OrderValidationError("Корзина пустая")

    delivery_method = _as_text(payload.get("deliveryMethod"))
    if delivery_method not in {"cdek", "yandex"}:
        raise OrderValidationError("Некорректный способ доставки")

    delivery_data = payload.get("deliveryData") or {}
    if not isinstance(delivery_data, dict):
        delivery_data = {}

    normalized_delivery = {
        "fullName": _as_text(delivery_data.get("fullName")),
        "phone": _as_text(delivery_data.get("phone")),
        "city": _as_text(delivery_data.get("city")),
        "address": _as_text(delivery_data.get("address")),
    }

    required = ["fullName", "phone", "city", "address"]
    if any(not normalized_delivery[field] for field in required):
        raise OrderValidationError("Заполните все данные доставки")

    products = await load_products()
    products_by_id = {product.get("id"): product for product in products}

    order_items: list[dict[str, Any]] = []
    total_price = 0

    for raw_item in items_in:
        if not isinstance(raw_item, dict):
            raise OrderValidationError("Некорректный товар в корзине")

        product_id = _as_text(raw_item.get("productId"))
        size = _as_text(raw_item.get("size")).upper()
        quantity = max(1, _as_int(raw_item.get("quantity"), 1))

        product = products_by_id.get(product_id)
        if not product or product.get("isActive", True) is False:
            raise OrderValidationError("Товар уже не в наличии")

        size_stock = product.get("sizeStock") or {}
        stock = _as_int(size_stock.get(size), 0)
        if stock < quantity:
            raise OrderValidationError(f"Размер {size} уже не в наличии")

        price = _as_int(product.get("price"), 0)
        total_price += price * quantity
        order_items.append(
            {
                "productId": product.get("id"),
                "productSnapshot": product,
                "brand": product.get("brand", ""),
                "name": product.get("name", ""),
                "size": size,
                "quantity": quantity,
                "price": price,
            }
        )

    username = _as_text(user.get("username"))
    telegram_id = _as_int(user.get("id"))
    if telegram_id <= 0:
        raise OrderValidationError("Не удалось определить Telegram ID")

    order = {
        "id": str(uuid.uuid4()),
        "orderNumber": None,
        "telegramId": telegram_id,
        "username": username,
        "clientOrderId": _as_text(payload.get("clientOrderId")) or None,
        "items": order_items,
        "totalPrice": total_price,
        "currency": "RUB",
        "deliveryMethod": delivery_method,
        "deliveryData": normalized_delivery,
        "comment": _as_text(payload.get("comment")),
        "status": "awaiting_payment",
        "paymentProofPhotoId": None,
    }
    return await create_order(order)
