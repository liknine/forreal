import base64
import json
import time
from pathlib import Path
from typing import Any

import httpx
from aiogram import Bot

from config import config
from utils import now_iso


def relative_image_path(filename: str) -> str:
    return f"{config.github_images_dir.strip('/')}/{filename}".replace("\\", "/")



def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def product_has_stock(product: dict[str, Any]) -> bool:
    size_stock = product.get("sizeStock") or {}
    if not isinstance(size_stock, dict):
        return False
    sizes = product.get("sizes") or list(size_stock.keys())
    for size in sizes:
        if _to_int(size_stock.get(str(size).upper(), size_stock.get(size)), 0) > 0:
            return True
    return False


def normalize_product_state(product: dict[str, Any]) -> dict[str, Any]:
    """Keep product visibility/discount safe before saving products.json.

    - Invalid discounts are removed.
    - Products with zero stock are hidden from the public catalog, not physically deleted.
    - If a product was hidden automatically because of zero stock and admin adds stock back,
      it becomes visible again. Manual hidden products stay hidden.
    """
    price = _to_int(product.get("price"), 0)
    discount_price = _to_int(product.get("discountPrice"), 0)

    if price <= 0 or discount_price <= 0 or discount_price >= price:
        product.pop("discountPrice", None)
    else:
        product["discountPrice"] = discount_price

    has_stock = product_has_stock(product)
    if not has_stock:
        product["isActive"] = False
        product["autoHiddenNoStock"] = True
        product.setdefault("soldOutAt", now_iso())
    elif product.get("autoHiddenNoStock"):
        product["isActive"] = True
        product["autoHiddenNoStock"] = False
        product.pop("soldOutAt", None)

    return product

async def ensure_products_file() -> None:
    config.products_path.parent.mkdir(parents=True, exist_ok=True)
    if not config.products_path.exists():
        config.products_path.write_text("[]", encoding="utf-8")
    config.images_dir.mkdir(parents=True, exist_ok=True)


async def load_products() -> list[dict[str, Any]]:
    await ensure_products_file()
    try:
        data = json.loads(config.products_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


async def save_products(products: list[dict[str, Any]]) -> None:
    await ensure_products_file()
    config.products_path.write_text(
        json.dumps(products, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def get_active_products() -> list[dict[str, Any]]:
    products = await load_products()
    return [product for product in products if product.get("isActive", True)]


async def find_product(product_id: str) -> dict[str, Any] | None:
    products = await load_products()
    for product in products:
        if product.get("id") == product_id:
            return product
    return None


async def decrease_stock(items: list[dict[str, Any]]) -> None:
    products = await load_products()
    by_id = {product.get("id"): product for product in products}

    for item in items:
        product = by_id.get(item.get("productId"))
        if not product:
            continue
        size = str(item.get("size", ""))
        quantity = int(item.get("quantity") or 1)
        size_stock = product.setdefault("sizeStock", {})
        current = int(size_stock.get(size, 0) or 0)
        size_stock[size] = max(0, current - quantity)
        product["updatedAt"] = now_iso()
        normalize_product_state(product)

    await save_products(products)
    try:
        await push_products_to_github("Update stock after payment")
    except Exception:
        # Local stock was already saved. Do not raise here; order status must not get stuck
        # and repeated status clicks must not double-decrease stock. Admin can run sync after fixing token.
        pass


async def add_or_update_product(product: dict[str, Any]) -> dict[str, Any]:
    product = normalize_product_state(dict(product))
    products = await load_products()
    found = False
    for index, existing in enumerate(products):
        if existing.get("id") == product.get("id"):
            product.setdefault("createdAt", existing.get("createdAt") or now_iso())
            product["updatedAt"] = now_iso()
            products[index] = product
            found = True
            break
    if not found:
        product.setdefault("createdAt", now_iso())
        product.setdefault("isActive", True)
        products.append(product)
    await save_products(products)
    await push_product_assets_to_github(product, "Add or update product")
    return product


async def toggle_product_active(product_id: str, is_active: bool) -> dict[str, Any] | None:
    products = await load_products()
    result = None
    for product in products:
        if product.get("id") == product_id:
            if is_active and not product_has_stock(product):
                product["isActive"] = False
                product["autoHiddenNoStock"] = True
                product.setdefault("soldOutAt", now_iso())
            else:
                product["isActive"] = is_active
                if is_active:
                    product["autoHiddenNoStock"] = False
                    product.pop("soldOutAt", None)
            product["updatedAt"] = now_iso()
            result = product
            break
    await save_products(products)
    await push_products_to_github("Toggle product visibility")
    return result


async def delete_product(product_id: str) -> bool:
    products = await load_products()
    filtered = [product for product in products if product.get("id") != product_id]
    if len(filtered) == len(products):
        return False
    await save_products(filtered)
    await push_products_to_github("Delete product")
    return True


async def save_product_photos(bot: Bot, product_id: str, photos: list[dict[str, str]]) -> list[str]:
    """Download Telegram photos/documents and return public relative image paths."""
    await ensure_products_file()
    image_paths: list[str] = []

    for index, item in enumerate(photos, start=1):
        file_id = item["file_id"]
        ext = item.get("ext") or ".jpg"
        if not ext.startswith("."):
            ext = f".{ext}"
        filename = f"{product_id}-{index}{ext.lower()}"
        local_path = config.images_dir / filename
        await bot.download(file_id, destination=local_path)
        image_paths.append(relative_image_path(filename))

    return image_paths


async def save_user_avatar(bot: Bot, user_id: int) -> str:
    """Download the user's current Telegram avatar, push it to GitHub, and return a public relative URL.

    This is only a UI fallback for the profile screen. Orders and security still use Telegram/bot data.
    """
    if not config.github_token:
        print(f"USER AVATAR SKIPPED {user_id}: GITHUB_TOKEN is empty")
        return ""

    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
    except Exception as exc:
        print(f"USER AVATAR READ FAILED {user_id}: {exc}")
        return ""

    if not photos.total_count or not photos.photos:
        print(f"USER AVATAR MISSING {user_id}: Telegram returned no profile photos. Check avatar privacy settings.")
        return ""

    try:
        best_photo = photos.photos[0][-1]
        avatars_dir = config.images_dir.parent / "avatars"
        avatars_dir.mkdir(parents=True, exist_ok=True)
        filename = f"user-{user_id}.jpg"
        local_path = avatars_dir / filename
        await bot.download(best_photo.file_id, destination=local_path)

        github_path = f"images/avatars/{filename}"
        async with httpx.AsyncClient(timeout=45) as client:
            await put_github_file(client, github_path, local_path.read_bytes(), "Update user avatar")

        avatar_url = f"{github_path}?v={int(time.time())}"
        print(f"USER AVATAR SYNCED {user_id}: {avatar_url}")
        return avatar_url
    except Exception as exc:
        print(f"USER AVATAR SYNC FAILED {user_id}: {exc}")
        return ""



async def load_settings() -> dict[str, Any]:
    """Load editable shop settings stored in data/settings.json."""
    path = config.settings_path
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


async def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    config.settings_path.parent.mkdir(parents=True, exist_ok=True)
    clean = dict(settings or {})
    clean["updatedAt"] = now_iso()
    config.settings_path.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return clean


def get_payment_text_sync() -> str:
    """Sync helper for message builders: custom admin text or .env fallback."""
    try:
        if config.settings_path.exists():
            data = json.loads(config.settings_path.read_text(encoding="utf-8"))
            value = str((data or {}).get("paymentText") or "").strip()
            if value:
                return value
    except Exception:
        pass
    return config.payment_card


async def save_payment_text(text: str) -> dict[str, Any]:
    settings = await load_settings()
    settings["paymentText"] = str(text or "").strip()
    settings = await save_settings(settings)
    await push_settings_to_github("Update payment details")
    return settings


async def save_home_hero_image(bot: Bot, file_id: str, ext: str = ".jpg") -> dict[str, Any]:
    """Save custom home hero image and publish settings + image to GitHub."""
    if not ext.startswith("."):
        ext = f".{ext}"
    ext = ext.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"

    config.assets_dir.mkdir(parents=True, exist_ok=True)
    filename = f"home-hero-custom{ext}"
    local_path = config.assets_dir / filename
    await bot.download(file_id, destination=local_path)

    settings = await load_settings()
    settings["homeHeroImage"] = f"assets/{filename}"
    settings["homeHeroVersion"] = int(time.time())
    settings = await save_settings(settings)

    if config.github_token:
        async with httpx.AsyncClient(timeout=60) as client:
            await put_github_file(client, f"assets/{filename}", local_path.read_bytes(), "Update home hero image")
            await put_github_file(client, config.github_settings_path, config.settings_path.read_bytes(), "Update shop settings")
    return settings


async def remove_home_hero_image() -> dict[str, Any]:
    """Disable custom home hero image. The physical file stays on GitHub for safety/cache stability."""
    settings = await load_settings()
    settings.pop("homeHeroImage", None)
    settings["homeHeroVersion"] = int(time.time())
    settings = await save_settings(settings)
    await push_settings_to_github("Reset home hero image")
    return settings


async def push_settings_to_github(message: str = "Update shop settings") -> None:
    if not config.github_token:
        return
    if not config.settings_path.exists():
        await save_settings(await load_settings())
    async with httpx.AsyncClient(timeout=30) as client:
        await put_github_file(
            client,
            config.github_settings_path,
            config.settings_path.read_bytes(),
            message,
        )

def github_api_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {config.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def get_github_file_sha(client: httpx.AsyncClient, path: str) -> str | None:
    if not config.github_token:
        return None
    url = f"https://api.github.com/repos/{config.github_repo}/contents/{path.lstrip('/')}"
    response = await client.get(url, headers=github_api_headers(), params={"ref": config.github_branch})
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data.get("sha")


async def put_github_file(client: httpx.AsyncClient, path: str, content: bytes, message: str) -> None:
    if not config.github_token:
        return
    clean_path = path.lstrip("/")
    url = f"https://api.github.com/repos/{config.github_repo}/contents/{clean_path}"
    sha = await get_github_file_sha(client, clean_path)
    payload = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": config.github_branch,
    }
    if sha:
        payload["sha"] = sha
    response = await client.put(url, headers=github_api_headers(), json=payload)
    response.raise_for_status()


async def push_products_to_github(message: str = "Update products.json") -> None:
    if not config.github_token:
        return
    await ensure_products_file()
    async with httpx.AsyncClient(timeout=30) as client:
        await put_github_file(
            client,
            config.github_products_path,
            config.products_path.read_bytes(),
            message,
        )


async def push_product_assets_to_github(product: dict[str, Any], message: str = "Update product assets") -> None:
    if not config.github_token:
        return
    await ensure_products_file()
    async with httpx.AsyncClient(timeout=60) as client:
        for image_path in product.get("images") or []:
            filename = str(image_path).split("/")[-1]
            candidate = config.images_dir / filename
            if candidate.exists():
                await put_github_file(client, image_path, candidate.read_bytes(), message)
        await put_github_file(
            client,
            config.github_products_path,
            config.products_path.read_bytes(),
            message,
        )


async def push_all_local_files_to_github() -> None:
    if not config.github_token:
        return
    await ensure_products_file()
    products = await load_products()
    async with httpx.AsyncClient(timeout=90) as client:
        for product in products:
            for image_path in product.get("images") or []:
                filename = str(image_path).split("/")[-1]
                candidate = config.images_dir / filename
                if candidate.exists():
                    await put_github_file(client, image_path, candidate.read_bytes(), "Sync product images")
        await put_github_file(
            client,
            config.github_products_path,
            config.products_path.read_bytes(),
            "Sync products.json",
        )
        if config.orders_public_path.exists():
            await put_github_file(
                client,
                config.github_orders_public_path,
                config.orders_public_path.read_bytes(),
                "Sync public orders",
            )
        if config.settings_path.exists():
            await put_github_file(
                client,
                config.github_settings_path,
                config.settings_path.read_bytes(),
                "Sync shop settings",
            )
        for hero_path in config.assets_dir.glob("home-hero-custom.*"):
            if hero_path.is_file():
                await put_github_file(client, f"assets/{hero_path.name}", hero_path.read_bytes(), "Sync home hero image")


async def push_to_github() -> None:
    await push_all_local_files_to_github()


def _public_order_item(item: dict[str, Any]) -> dict[str, Any]:
    snapshot = item.get("productSnapshot") or {}
    images = snapshot.get("images") or []
    image = ""
    if isinstance(images, list) and images:
        image = str(images[0] or "")
    if not image:
        image = str(snapshot.get("detailImage") or "")
    return {
        "productId": item.get("productId"),
        "brand": item.get("brand", ""),
        "name": item.get("name", ""),
        "size": item.get("size", ""),
        "quantity": int(item.get("quantity") or 1),
        "price": int(item.get("price") or 0),
        "image": image,
    }


def public_order(order: dict[str, Any]) -> dict[str, Any]:
    """Safe public order payload for GitHub Pages.

    Do not include fullName, phone, city, address, comment, payment proof or raw snapshots.
    """
    return {
        "id": order.get("id"),
        "orderNumber": order.get("orderNumber"),
        "clientOrderId": order.get("clientOrderId"),
        "telegramId": int(order.get("telegramId") or 0),
        "username": order.get("username") or "",
        "items": [_public_order_item(item) for item in (order.get("items") or []) if isinstance(item, dict)],
        "totalPrice": int(order.get("totalPrice") or 0),
        "currency": order.get("currency") or "RUB",
        "deliveryMethod": order.get("deliveryMethod") or "",
        "status": order.get("status") or "awaiting_payment",
        "createdAt": order.get("createdAt") or "",
        "updatedAt": order.get("updatedAt") or order.get("createdAt") or "",
    }


async def save_public_orders(orders: list[dict[str, Any]]) -> None:
    config.orders_public_path.parent.mkdir(parents=True, exist_ok=True)
    safe_orders = [public_order(order) for order in orders if isinstance(order, dict)]
    config.orders_public_path.write_text(
        json.dumps(safe_orders, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def push_public_orders_to_github(message: str = "Update public orders") -> None:
    if not config.github_token:
        return
    if not config.orders_public_path.exists():
        config.orders_public_path.parent.mkdir(parents=True, exist_ok=True)
        config.orders_public_path.write_text("[]", encoding="utf-8")
    async with httpx.AsyncClient(timeout=30) as client:
        await put_github_file(
            client,
            config.github_orders_public_path,
            config.orders_public_path.read_bytes(),
            message,
        )
