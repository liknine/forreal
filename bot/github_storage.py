import base64
import json
from pathlib import Path
from typing import Any

import httpx
from aiogram import Bot

from config import config
from utils import now_iso


def relative_image_path(filename: str) -> str:
    return f"{config.github_images_dir.strip('/')}/{filename}".replace("\\", "/")


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

    await save_products(products)
    await push_products_to_github("Update stock after payment")


async def add_or_update_product(product: dict[str, Any]) -> dict[str, Any]:
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
            product["isActive"] = is_active
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
            local_path = config.PROJECT_ROOT / image_path if hasattr(config, "PROJECT_ROOT") else None
            # config has no PROJECT_ROOT field, so use images_dir and filename instead.
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


async def push_to_github() -> None:
    await push_all_local_files_to_github()
