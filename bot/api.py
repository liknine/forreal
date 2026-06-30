import uuid
from typing import Literal

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import config
from db import create_order, get_order, get_orders_for_user, get_recent_orders, init_db, update_order_status
from github_storage import (
    decrease_stock,
    delete_product,
    get_active_products,
    load_products,
    toggle_product_active,
)
from keyboards import client_payment_kb, admin_order_kb
from utils import (
    DELIVERY_LABELS,
    STATUS_LABELS,
    code,
    escape_html,
    format_price,
    verify_telegram_init_data,
)

app = FastAPI(title="ForReal Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OrderItemIn(BaseModel):
    productId: str
    size: str
    quantity: int = Field(default=1, ge=1, le=99)


class DeliveryDataIn(BaseModel):
    fullName: str = ""
    phone: str = ""
    city: str = ""
    address: str = ""


class OrderCreateIn(BaseModel):
    clientOrderId: str | None = None
    items: list[OrderItemIn]
    deliveryMethod: Literal["cdek", "yandex"]
    deliveryData: DeliveryDataIn
    comment: str = ""


class ProductPatchIn(BaseModel):
    isActive: bool | None = None


class OrderStatusPatchIn(BaseModel):
    status: Literal["awaiting_payment", "paid", "in_delivery", "awaiting_pickup", "closed", "canceled"]


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "forreal-backend"}


@app.get("/api/products")
async def api_products() -> list[dict]:
    products = await get_active_products()
    return sorted(products, key=lambda item: item.get("createdAt", ""), reverse=True)


@app.post("/api/orders")
async def api_create_order(
    payload: OrderCreateIn,
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
) -> dict:
    if not payload.items:
        raise HTTPException(status_code=400, detail="Корзина пустая")

    try:
        user = verify_telegram_init_data(x_telegram_init_data)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    products = await load_products()
    products_by_id = {product.get("id"): product for product in products}

    order_items: list[dict] = []
    total_price = 0

    for raw_item in payload.items:
        product = products_by_id.get(raw_item.productId)
        if not product or not product.get("isActive", True):
            raise HTTPException(status_code=400, detail="Товар уже не в наличии")

        size_stock = product.get("sizeStock") or {}
        stock = int(size_stock.get(raw_item.size, 0) or 0)
        if stock < raw_item.quantity:
            raise HTTPException(status_code=400, detail=f"Размер {raw_item.size} уже не в наличии")

        price = int(product.get("price") or 0)
        total_price += price * raw_item.quantity
        order_items.append(
            {
                "productId": product.get("id"),
                "productSnapshot": product,
                "brand": product.get("brand", ""),
                "name": product.get("name", ""),
                "size": raw_item.size,
                "quantity": raw_item.quantity,
                "price": price,
            }
        )

    order = {
        "id": str(uuid.uuid4()),
        "orderNumber": None,
        "telegramId": int(user["id"]),
        "username": user.get("username", ""),
        "clientOrderId": payload.clientOrderId,
        "items": order_items,
        "totalPrice": total_price,
        "currency": "RUB",
        "deliveryMethod": payload.deliveryMethod,
        "deliveryData": payload.deliveryData.model_dump(),
        "comment": payload.comment,
        "status": "awaiting_payment",
        "paymentProofPhotoId": None,
    }

    created = await create_order(order)
    await notify_order_created(created)
    return created


@app.get("/api/orders/my")
async def api_my_orders(
    x_telegram_init_data: str = Header(default="", alias="X-Telegram-Init-Data"),
) -> list[dict]:
    try:
        user = verify_telegram_init_data(x_telegram_init_data)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return await get_orders_for_user(int(user["id"]))


@app.get("/api/admin/products")
async def api_admin_products(x_admin_token: str = Header(default="", alias="X-Admin-Token")) -> list[dict]:
    verify_admin_token(x_admin_token)
    return await load_products()


@app.patch("/api/admin/products/{product_id}")
async def api_admin_patch_product(
    product_id: str,
    payload: ProductPatchIn,
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
) -> dict:
    verify_admin_token(x_admin_token)
    if payload.isActive is None:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    product = await toggle_product_active(product_id, payload.isActive)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


@app.delete("/api/admin/products/{product_id}")
async def api_admin_delete_product(
    product_id: str,
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
) -> dict:
    verify_admin_token(x_admin_token)
    ok = await delete_product(product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return {"ok": True}


@app.get("/api/admin/orders")
async def api_admin_orders(x_admin_token: str = Header(default="", alias="X-Admin-Token")) -> list[dict]:
    verify_admin_token(x_admin_token)
    return await get_recent_orders(limit=100)


@app.patch("/api/admin/orders/{order_id}/status")
async def api_admin_order_status(
    order_id: str,
    payload: OrderStatusPatchIn,
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
) -> dict:
    verify_admin_token(x_admin_token)
    before = await get_order(order_id)
    if not before:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if payload.status == "paid" and before["status"] != "paid":
        await decrease_stock(before["items"])
    order = await update_order_status(order_id, payload.status)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return order


def verify_admin_token(token: str) -> None:
    if not config.admin_api_token:
        raise HTTPException(status_code=403, detail="ADMIN_API_TOKEN не настроен")
    if token != config.admin_api_token:
        raise HTTPException(status_code=403, detail="Нет доступа")


async def notify_order_created(order: dict) -> None:
    if not config.bot_token:
        return

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        admin_text = build_admin_order_text(order)
        for admin_id in config.admin_ids:
            await bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=admin_order_kb(order["id"]),
            )

        await bot.send_message(
            chat_id=order["telegramId"],
            text=build_client_payment_text(order),
            reply_markup=client_payment_kb(order["id"]),
        )
    finally:
        await bot.session.close()


def build_client_payment_text(order: dict) -> str:
    return (
        f"Заказ #{order['orderNumber']} создан.\n\n"
        f"Сумма к оплате: {code(format_price(order['totalPrice']))}\n\n"
        f"Реквизиты:\n{code(config.payment_card)}\n\n"
        "После оплаты нажмите кнопку ОТПРАВИТЬ ЧЕК и отправьте фото перевода."
    )


def build_admin_order_text(order: dict) -> str:
    lines = [
        f"🧾 Новый заказ #{order['orderNumber']}",
        "",
        f"Клиент: @{escape_html(order.get('username') or 'без username')}",
        f"Telegram ID: {code(order['telegramId'])}",
        "",
        "🛍 Товары:",
    ]

    for index, item in enumerate(order["items"], start=1):
        lines.extend(
            [
                f"{index}. {code(item.get('brand', ''))}",
                f"   {code(item.get('name', ''))}",
                f"   Размер: {code(item.get('size', ''))}",
                f"   Цена: {code(format_price(item.get('price', 0)))}",
                "",
            ]
        )

    delivery = order.get("deliveryData", {}) or {}
    lines.extend(
        [
            f"Итого: {code(format_price(order.get('totalPrice', 0)))}",
            "",
            f"Доставка: {code(DELIVERY_LABELS.get(order.get('deliveryMethod'), order.get('deliveryMethod')))}",
            "",
            f"ФИО: {code(delivery.get('fullName', ''))}",
            f"Телефон: {code(delivery.get('phone', ''))}",
            f"Город: {code(delivery.get('city', ''))}",
            f"ПВЗ / адрес: {code(delivery.get('address', ''))}",
            "",
            "Комментарий:",
            code(order.get("comment") or "—"),
            "",
            f"Статус: {code(STATUS_LABELS.get(order.get('status'), order.get('status')))}",
        ]
    )
    return "\n".join(lines)
