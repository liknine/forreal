import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BOT_DIR.parent
load_dotenv(BOT_DIR / ".env")


def parse_admin_ids(value: str) -> set[int]:
    ids: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Category:
    key: str
    label: str


CATEGORIES: tuple[Category, ...] = (
    Category("tees", "ФУТБОЛКИ"),
    Category("hoodies", "ХУДИ"),
    Category("zip_hoodies", "ЗИП-ХУДИ"),
    Category("shorts", "ШОРТЫ"),
    Category("pants", "ШТАНЫ"),
    Category("accessories", "АКСЕССУАРЫ"),
    Category("shoes", "ОБУВЬ"),
)

CATEGORY_LABELS = {category.key: category.label for category in CATEGORIES}
CATEGORY_KEYS_BY_LABEL = {category.label: category.key for category in CATEGORIES}


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: set[int]
    mini_app_url: str
    api_host: str
    api_port: int
    cors_origins: list[str]
    admin_api_token: str
    github_token: str
    github_repo: str
    github_branch: str
    github_products_path: str
    github_images_dir: str
    github_orders_public_path: str
    github_settings_path: str
    database_path: Path
    products_path: Path
    images_dir: Path
    orders_public_path: Path
    settings_path: Path
    assets_dir: Path
    payment_card: str
    pickup_admin_username: str


config = Config(
    bot_token=os.getenv("BOT_TOKEN", ""),
    admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    mini_app_url=os.getenv("MINI_APP_URL", "https://liknine.github.io/forreal/"),
    api_host=os.getenv("API_HOST", "0.0.0.0"),
    api_port=int(os.getenv("API_PORT", "8000")),
    cors_origins=split_csv(os.getenv("BACKEND_CORS_ORIGINS", "*")),
    admin_api_token=os.getenv("ADMIN_API_TOKEN", ""),
    github_token=os.getenv("GITHUB_TOKEN", ""),
    github_repo=os.getenv("GITHUB_REPO", "liknine/forreal"),
    github_branch=os.getenv("GITHUB_BRANCH", "main"),
    github_products_path=os.getenv("GITHUB_PRODUCTS_PATH", "data/products.json"),
    github_images_dir=os.getenv("GITHUB_IMAGES_DIR", "images/products"),
    github_orders_public_path=os.getenv("GITHUB_ORDERS_PUBLIC_PATH", "data/orders_public.json"),
    github_settings_path=os.getenv("GITHUB_SETTINGS_PATH", "data/settings.json"),
    database_path=PROJECT_ROOT / os.getenv("DATABASE_PATH", "forreal.sqlite3"),
    products_path=PROJECT_ROOT / os.getenv("GITHUB_PRODUCTS_PATH", "data/products.json"),
    images_dir=PROJECT_ROOT / os.getenv("GITHUB_IMAGES_DIR", "images/products"),
    orders_public_path=PROJECT_ROOT / os.getenv("GITHUB_ORDERS_PUBLIC_PATH", "data/orders_public.json"),
    settings_path=PROJECT_ROOT / os.getenv("GITHUB_SETTINGS_PATH", "data/settings.json"),
    assets_dir=PROJECT_ROOT / "assets",
    payment_card=os.getenv("PAYMENT_CARD", "XXXX-XXXX-XXXX-XXXX"),
    pickup_admin_username=os.getenv("PICKUP_ADMIN_USERNAME", "woodyqqqq").lstrip("@"),
)
