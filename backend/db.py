"""Shared SQLite helpers for the API routes, auth, and agent tools."""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
PRODUCTS_DIR = DATA_DIR / "products"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def connect_ro() -> sqlite3.Connection:
    """Read-only connection: catalogue browsing and every agent tool use this."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_rw() -> sqlite3.Connection:
    """Writable connection: only accounts/sessions (auth.py) use this."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def product_from_row(row: sqlite3.Row) -> dict:
    product = dict(row)
    product["colors"] = json.loads(product["colors"])
    product["search_tags"] = json.loads(product["search_tags"])
    # image_file_path is "products/<file>.jpg"; exposed under the /media mount.
    product["image_url"] = f"/media/{product['image_file_path']}"
    return product


def inventory_for(conn: sqlite3.Connection, product_id: str) -> list[dict]:
    rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()
    order = {size: i for i, size in enumerate(SIZE_ORDER)}
    return sorted(
        ({"size": r["size"], "quantity": r["quantity"]} for r in rows),
        key=lambda item: order.get(item["size"], len(order)),
    )


def get_product(conn: sqlite3.Connection, product_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    if row is None:
        return None
    product = product_from_row(row)
    product["inventory"] = inventory_for(conn, product_id)
    product["total_stock"] = sum(item["quantity"] for item in product["inventory"])
    return product
