import json
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

from config import config
from utils import now_iso


@asynccontextmanager
async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(config.database_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    async with get_db() as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                order_number INTEGER UNIQUE NOT NULL,
                telegram_id INTEGER NOT NULL,
                username TEXT,
                client_order_id TEXT,
                total_price INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'RUB',
                delivery_method TEXT NOT NULL,
                delivery_data_json TEXT NOT NULL,
                comment TEXT,
                status TEXT NOT NULL,
                payment_proof_photo_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                product_snapshot_json TEXT NOT NULL,
                brand TEXT,
                name TEXT,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_telegram_id ON orders(telegram_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)"
        )
        await db.commit()


async def next_order_number(db: aiosqlite.Connection) -> int:
    async with db.execute("SELECT MAX(order_number) AS max_number FROM orders") as cursor:
        row = await cursor.fetchone()
    max_number = row["max_number"] if row and row["max_number"] else 1000
    return int(max_number) + 1


async def create_order(order: dict[str, Any]) -> dict[str, Any]:
    async with get_db() as db:
        order_number = await next_order_number(db)
        created_at = now_iso()
        updated_at = created_at
        order["orderNumber"] = order_number
        order["createdAt"] = created_at
        order["updatedAt"] = updated_at

        await db.execute(
            """
            INSERT INTO orders (
                id, order_number, telegram_id, username, client_order_id,
                total_price, currency, delivery_method, delivery_data_json,
                comment, status, payment_proof_photo_id, payload_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order["id"],
                order_number,
                order["telegramId"],
                order.get("username"),
                order.get("clientOrderId"),
                order["totalPrice"],
                order.get("currency", "RUB"),
                order["deliveryMethod"],
                json.dumps(order.get("deliveryData", {}), ensure_ascii=False),
                order.get("comment", ""),
                order["status"],
                order.get("paymentProofPhotoId"),
                json.dumps(order, ensure_ascii=False),
                created_at,
                updated_at,
            ),
        )

        for item in order["items"]:
            await db.execute(
                """
                INSERT INTO order_items (
                    order_id, product_id, product_snapshot_json, brand, name,
                    size, quantity, price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order["id"],
                    item["productId"],
                    json.dumps(item.get("productSnapshot", {}), ensure_ascii=False),
                    item.get("brand"),
                    item.get("name"),
                    item["size"],
                    item["quantity"],
                    item["price"],
                ),
            )

        await db.commit()
        return order


async def row_to_order(row: aiosqlite.Row, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "orderNumber": row["order_number"],
        "telegramId": row["telegram_id"],
        "username": row["username"],
        "clientOrderId": row["client_order_id"],
        "items": items,
        "totalPrice": row["total_price"],
        "currency": row["currency"],
        "deliveryMethod": row["delivery_method"],
        "deliveryData": json.loads(row["delivery_data_json"] or "{}"),
        "comment": row["comment"] or "",
        "status": row["status"],
        "paymentProofPhotoId": row["payment_proof_photo_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


async def get_order(order_id: str) -> dict[str, Any] | None:
    async with get_db() as db:
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
            order_row = await cursor.fetchone()
        if not order_row:
            return None
        async with db.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,)) as cursor:
            item_rows = await cursor.fetchall()
        items = [
            {
                "productId": item["product_id"],
                "productSnapshot": json.loads(item["product_snapshot_json"] or "{}"),
                "brand": item["brand"],
                "name": item["name"],
                "size": item["size"],
                "quantity": item["quantity"],
                "price": item["price"],
            }
            for item in item_rows
        ]
        return await row_to_order(order_row, items)


async def get_orders_for_user(telegram_id: int) -> list[dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM orders WHERE telegram_id = ? ORDER BY order_number DESC",
            (telegram_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            async with db.execute("SELECT * FROM order_items WHERE order_id = ?", (row["id"],)) as cursor:
                item_rows = await cursor.fetchall()
            items = [
                {
                    "productId": item["product_id"],
                    "productSnapshot": json.loads(item["product_snapshot_json"] or "{}"),
                    "brand": item["brand"],
                    "name": item["name"],
                    "size": item["size"],
                    "quantity": item["quantity"],
                    "price": item["price"],
                }
                for item in item_rows
            ]
            result.append(await row_to_order(row, items))
        return result


async def get_recent_orders(limit: int = 20) -> list[dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM orders ORDER BY order_number DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            async with db.execute("SELECT * FROM order_items WHERE order_id = ?", (row["id"],)) as cursor:
                item_rows = await cursor.fetchall()
            items = [
                {
                    "productId": item["product_id"],
                    "productSnapshot": json.loads(item["product_snapshot_json"] or "{}"),
                    "brand": item["brand"],
                    "name": item["name"],
                    "size": item["size"],
                    "quantity": item["quantity"],
                    "price": item["price"],
                }
                for item in item_rows
            ]
            result.append(await row_to_order(row, items))
        return result


async def update_order_status(order_id: str, status: str) -> dict[str, Any] | None:
    updated_at = now_iso()
    async with get_db() as db:
        await db.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
            (status, updated_at, order_id),
        )
        async with db.execute("SELECT payload_json FROM orders WHERE id = ?", (order_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            payload = json.loads(row["payload_json"])
            payload["status"] = status
            payload["updatedAt"] = updated_at
            await db.execute(
                "UPDATE orders SET payload_json = ? WHERE id = ?",
                (json.dumps(payload, ensure_ascii=False), order_id),
            )
        await db.commit()
    return await get_order(order_id)


async def set_payment_proof(order_id: str, photo_id: str) -> dict[str, Any] | None:
    updated_at = now_iso()
    async with get_db() as db:
        await db.execute(
            "UPDATE orders SET payment_proof_photo_id = ?, updated_at = ? WHERE id = ?",
            (photo_id, updated_at, order_id),
        )
        await db.commit()
    return await get_order(order_id)
