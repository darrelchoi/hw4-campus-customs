"""Tools the Campus Customs chatbot can call.

Every read tool opens the database with mode=ro, so the agent can
never change prices, stock, or accounts. Price and stock answers must come from here.

Each tool also records the prices/quantities it returned in ShopDeps, so the
output validator in agent.py can double-check the final reply against them.
"""

import fcntl
import functools
import inspect
import json
import logging
import re
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai import RunContext

from models import (
    LOW_STOCK_THRESHOLD,
    CustomerContext,
    LookupFailed,
    PageContext,
    PriceInfo,
    ProductInfo,
    ProductMatch,
    ProductSummary,
    RestockAlert,
    RestockAlertList,
    RestockAlertResult,
    SearchResult,
    ShopDeps,
    SizeStockLine,
    StockReport,
    StockStatus,
)

MAX_RESULTS = 12

# Shopper words -> words that appear in the catalogue.
SYNONYMS = {
    "tee": "t-shirt", "tees": "t-shirt", "tshirt": "t-shirt", "tshirts": "t-shirt", "shirts": "shirt",
    "hoody": "hoodie", "hoodies": "hoodie", "hooded": "hood",
    "sweatshirts": "sweatshirt", "crewnecks": "crewneck",
    "quarterzip": "quarter-zip", "1/4": "quarter-zip",
    "jackets": "jacket", "fleeces": "fleece", "grey": "gray",
}
STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "of", "to", "do", "you", "have", "any", "some",
    "me", "i", "want", "looking", "need", "show", "yale", "campus", "customs", "merch", "items", "item",
}

# Shopper size words -> DB sizes.
SIZE_ALIASES = {
    "xs": "XS", "extra small": "XS", "x-small": "XS", "xsmall": "XS",
    "s": "S", "small": "S", "sm": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L", "lg": "L",
    "xl": "XL", "extra large": "XL", "x-large": "XL", "xlarge": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "xxlarge": "XXL", "double xl": "XXL",
}

# Paraphrased from yalebulldogblue.com (see output/site_research.md).
STORE_INFO = {
    "location": "Campus Customs is at 57 Broadway, New Haven, CT 06511, a short walk from Yale's campus.",
    "hours": "The Broadway store is open 7 days a week. Exact hours are not in our system, so suggest calling (475) 301-4205.",
    "contact": "Order help: orderdept@campuscustoms.com or (475) 301-4205.",
    "returns": (
        "Returns are accepted within 30 days of shipping for unworn, unused items with original tags. "
        "Custom-made items (like custom alumni pieces) are final sale. To start a return, email your tracking "
        "number to orderdept@campuscustoms.com and ship with insured, trackable shipping. Refunds take 2-10 "
        "business days after the return arrives and do not include original shipping. The store pays return "
        "shipping only when the error was theirs."
    ),
    "shipping": "Campus Customs ships within the US and internationally to 25+ countries.",
    "custom_orders": (
        "Campus Customs does screen printing, embroidery, digital printing, and promotional items in-house "
        "for teams, clubs, reunions, and groups. Contact orderdept@campuscustoms.com for a quote."
    ),
    "history": (
        "Campus Customs opened on Broadway in 1975 and is New Haven's longest-running official Yale merchandise "
        "shop. Most printing and embroidery happens on site in the old York Square Cinema building."
    ),
    "ordering": (
        "This chat assistant cannot place orders, take payments, hold items, or apply discounts. Shoppers can "
        "visit the store or contact orderdept@campuscustoms.com."
    ),
}


# ---------- database access (SQLite data/campus_customs.db; also used by the web app's routes) ----------

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


# ---------- audit trail: append-only output/audit_trail.json (every tool call is wrapped) ----------
"""
The file is always a valid JSON array. New records are appended in place by overwriting only the
closing "]" (under an exclusive file lock), so earlier entries are never rewritten or wiped between runs.
Each record = one chat turn (see agent.run_chat): who (user_id or guest, never email), tool calls
(time, name, short args/result, ms, ok), double-check retries, usage, and the stop reason.
"""

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
MAX_FIELD = 240  # chars kept for args/results/messages: short, readable, and bounded file growth

log = logging.getLogger("uvicorn.error")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def audit_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def audit_short(value, limit: int = MAX_FIELD) -> str:
    """Compact one-line summary with emails redacted (the store's public address is kept)."""
    if isinstance(value, BaseModel):
        value = value.model_dump(exclude_none=True)
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text = _EMAIL_RE.sub(lambda m: m.group(0) if m.group(0).startswith("orderdept@") else "[email]", text)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def summarize_result(result) -> str:
    """Tool results can be large (12 search rows); keep the parts an auditor needs."""
    data = result.model_dump(exclude_none=True) if isinstance(result, BaseModel) else result
    if isinstance(data, dict) and "results" in data and "total_matches" in data:
        names = [r["name"] for r in data["results"][:4]]
        return audit_short(
            f"total_matches={data['total_matches']} shown={len(data['results'])} "
            f"price_range={data.get('price_range_display')} first={names}"
        )
    if isinstance(data, dict) and "sizes" in data and "summary" in data:  # StockReport
        return audit_short(f"{data['name']}: {data['summary']}")
    return audit_short(data)


def audited(tool):
    """Wrap a tool so every call is recorded in ctx.deps.audit_events (signature/docstring preserved for PydanticAI)."""

    @functools.wraps(tool)
    def wrapper(ctx, *args, **kwargs):
        started = time.perf_counter()
        bound = inspect.signature(tool).bind_partial(ctx, *args, **kwargs)
        call_args = {k: v for k, v in bound.arguments.items() if k != "ctx" and v not in (None, "", False)}
        event = {"t": audit_now(), "type": "tool_call", "tool": tool.__name__, "args": audit_short(call_args)}
        try:
            result = tool(ctx, *args, **kwargs)
        except Exception as exc:
            event.update(ok=False, result=audit_short(f"{type(exc).__name__}: {exc}"))
            raise
        else:
            failed = isinstance(result, BaseModel) and (getattr(result, "error", None) or getattr(result, "ok", True) is False)
            event.update(ok=not failed, result=summarize_result(result))
            return result
        finally:
            event["ms"] = round((time.perf_counter() - started) * 1000)
            ctx.deps.audit_events.append(event)

    return wrapper


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def audit_append(record: dict) -> None:
    """Append one record to the JSON array without touching existing entries. Never raises into the chat."""
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps(record, ensure_ascii=False, default=str, indent=2)
        entry = "\n".join("  " + line for line in entry.splitlines())
        with open(AUDIT_PATH, "a+b") as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # one writer at a time (concurrent chats, multiple workers)
            try:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    f.write(("[\n" + entry + "\n]\n").encode())
                    return
                # Find the final "]" and write ",\n<entry>\n]" over it: an in-place append.
                f.seek(max(0, size - 64))
                tail = f.read()
                close_at = tail.rfind(b"]")
                if close_at == -1:
                    raise ValueError("audit_trail.json does not end with ']'; refusing to modify it")
                before = tail[:close_at].rstrip()  # content up to the last "}" (or "[" if the array is empty)
                empty = before.endswith(b"[")
                write_at = size - len(tail) + len(before)
                # "a+" writes always go to the end, so rewrite the closing bracket through a second handle.
                with open(AUDIT_PATH, "r+b") as w:
                    w.seek(write_at)
                    w.write((("\n" if empty else ",\n") + entry + "\n]\n").encode())
                    w.truncate()  # only drops the old closing bracket/newline that were just overwritten
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        log.exception("audit trail append failed (chat continues)")


# ---------- restock alerts storage (table restock_alerts; the only table agent tools write to) ----------

MAX_ACTIVE_ALERTS = 10  # per shopper; stops runaway or abusive tool calls


def init_restock_table() -> None:
    with closing(connect_rw()) as conn, conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS restock_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                product_id TEXT NOT NULL REFERENCES catalogue(product_id),
                size TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                notified_at TEXT,
                UNIQUE (user_id, product_id, size)
            )"""
        )


_SELECT = """
    SELECT a.product_id, c.name, a.size, a.created_at, a.notified_at, COALESCE(i.quantity, 0) AS quantity
    FROM restock_alerts a
    JOIN catalogue c ON c.product_id = a.product_id
    LEFT JOIN inventory i ON i.product_id = a.product_id AND i.size = a.size
"""


def _alert(row) -> RestockAlert:
    return RestockAlert(
        product_id=row["product_id"],
        name=row["name"],
        size=row["size"],
        created_at=row["created_at"],
        current_quantity=row["quantity"],
        back_in_stock=row["quantity"] > 0,
    )


def active_alerts(user_id: int) -> list[RestockAlert]:
    """Alerts the shopper hasn't been notified about yet, with live stock."""
    with closing(connect_ro()) as conn:
        rows = conn.execute(_SELECT + " WHERE a.user_id = ? AND a.notified_at IS NULL ORDER BY a.id", (user_id,)).fetchall()
    return [_alert(r) for r in rows]


def create_alert(user_id: int, product_id: str, size: str) -> tuple[str, RestockAlert | None]:
    """Returns (status, alert). status: created | already_exists | limit."""
    with closing(connect_rw()) as conn, conn:
        existing = conn.execute(
            "SELECT 1 FROM restock_alerts WHERE user_id = ? AND product_id = ? AND size = ? AND notified_at IS NULL",
            (user_id, product_id, size),
        ).fetchone()
        if not existing:
            active = conn.execute(
                "SELECT COUNT(*) FROM restock_alerts WHERE user_id = ? AND notified_at IS NULL", (user_id,)
            ).fetchone()[0]
            if active >= MAX_ACTIVE_ALERTS:
                return "limit", None
            # A past, already-notified alert for the same size is re-armed.
            conn.execute(
                """INSERT INTO restock_alerts (user_id, product_id, size) VALUES (?, ?, ?)
                   ON CONFLICT (user_id, product_id, size)
                   DO UPDATE SET created_at = datetime('now'), notified_at = NULL""",
                (user_id, product_id, size),
            )
        row = conn.execute(
            _SELECT + " WHERE a.user_id = ? AND a.product_id = ? AND a.size = ?", (user_id, product_id, size)
        ).fetchone()
    return ("already_exists" if existing else "created"), _alert(row)


def cancel_alert(user_id: int, product_id: str, size: str) -> bool:
    with closing(connect_rw()) as conn, conn:
        return conn.execute(
            "DELETE FROM restock_alerts WHERE user_id = ? AND product_id = ? AND size = ? AND notified_at IS NULL",
            (user_id, product_id, size),
        ).rowcount > 0


def pop_restocked(user_id: int) -> list[RestockAlert]:
    """Alerts whose size is back in stock: returned once, then marked notified."""
    with closing(connect_rw()) as conn, conn:
        rows = conn.execute(
            _SELECT + " WHERE a.user_id = ? AND a.notified_at IS NULL AND COALESCE(i.quantity, 0) > 0", (user_id,)
        ).fetchall()
        for r in rows:
            conn.execute(
                "UPDATE restock_alerts SET notified_at = datetime('now') WHERE user_id = ? AND product_id = ? AND size = ?",
                (user_id, r["product_id"], r["size"]),
            )
    return [_alert(r) for r in rows]


# ---------- helpers ----------

def _terms(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9/\-]+", text.lower())
    return [SYNONYMS.get(w, w) for w in words if w not in STOPWORDS]


def _price_display(price: float) -> str:
    return f"${price:,.2f}"


def _status(quantity: int) -> StockStatus:
    if quantity == 0:
        return "sold_out"
    if quantity <= LOW_STOCK_THRESHOLD:
        return "low_stock"
    return "in_stock"


def normalize_size(size: str) -> str | None:
    key = size.strip().lower().replace(".", "")
    return SIZE_ALIASES.get(key) or (key.upper() if key.upper() in SIZE_ORDER else None)


def _resolve(conn, product: str) -> dict | LookupFailed:
    """Find one product by product_id, exact name, or unambiguous partial name."""
    text = product.strip()
    found = get_product(conn, text) or get_product(conn, text.lower().replace(" ", "-"))
    if found:
        return found
    rows = conn.execute("SELECT product_id, name FROM catalogue").fetchall()
    exact = [r for r in rows if r["name"].lower() == text.lower()]
    if len(exact) == 1:
        return get_product(conn, exact[0]["product_id"])
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]
    partial = [r for r in rows if words and all(w in r["name"].lower() for w in words)]
    if len(partial) == 1:
        return get_product(conn, partial[0]["product_id"])
    candidates = partial or [r for r in rows if any(w in r["name"].lower() for w in words)]
    return LookupFailed(
        error=(
            f"More than one product matches {product!r}. Ask the shopper which one, or use a product_id."
            if len(partial) > 1
            else f"No product matches {product!r}. Use search_products to find it."
        ),
        did_you_mean=[ProductMatch(product_id=r["product_id"], name=r["name"]) for r in candidates[:5]],
    )


def _log(ctx: RunContext[ShopDeps], call: str, status: str) -> None:
    """Record the call (server log / audit) and tell the shopper what's happening (streaming status)."""
    ctx.deps.tool_calls.append(call)
    if ctx.deps.on_status:
        ctx.deps.on_status(status)


def _pretty(product: str) -> str:
    """'crew-left-chest-hoodie' -> 'Crew Left Chest Hoodie' for status messages."""
    text = product.strip()
    return text.replace("-", " ").title() if "-" in text and " " not in text else text


# ---------- tools ----------

def search_products(
    ctx: RunContext[ShopDeps],
    query: str = "",
    color: str | None = None,
    size: str | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False,
) -> SearchResult | LookupFailed:
    """Search the catalogue to find and recommend products.

    Use this for browsing ("navy hoodies", "hockey gear", "something under $50").
    For a specific product's exact price or per-size stock, use get_price / check_stock instead.

    Args:
        query: Keywords such as "navy hoodie", "hockey", "Harvard game", "bulldog crewneck". Empty = all products.
        color: Only products whose colors include this word (e.g. "gray", "navy").
        size: Only products with this size IN STOCK (XS, S, M, L, XL, XXL). Items sold out in that size are hidden.
        max_price: Only products at or below this price in USD.
        in_stock_only: Only products with at least one unit in stock.
    """
    looking_for = " ".join(x for x in [color, query] if x) or "everything"
    _log(
        ctx,
        f"search_products(query={query!r}, color={color!r}, size={size!r}, max_price={max_price!r})",
        f"Searching the catalogue for {looking_for}" + (f" in size {size}" if size else "") + "…",
    )
    terms = _terms(query)
    wanted_size = normalize_size(size) if size else None
    if size and not wanted_size:
        return LookupFailed(error=f"Unknown size {size!r}. Sizes are {', '.join(SIZE_ORDER)}.")

    matches: list[tuple[int, ProductSummary]] = []
    with closing(connect_ro()) as conn:
        for row in conn.execute("SELECT * FROM catalogue").fetchall():
            product = product_from_row(row)
            haystack = " ".join(
                [product["name"], product["garment_type"], product["description"], *product["colors"], *product["search_tags"]]
            ).lower()
            score = sum(1 for t in terms if t in haystack)
            if terms and score == 0:
                continue
            if color and not any(color.lower() in c.lower() for c in product["colors"]):
                continue
            if max_price is not None and product["price"] > max_price:
                continue
            inventory = inventory_for(conn, product["product_id"])
            summary = ProductSummary(
                product_id=product["product_id"],
                name=product["name"],
                garment_type=product["garment_type"],
                price=product["price"],
                colors=product["colors"],
                total_stock=sum(i["quantity"] for i in inventory),
                sizes_in_stock=[i["size"] for i in inventory if i["quantity"] > 0],
                sizes_sold_out=[i["size"] for i in inventory if i["quantity"] == 0],
            )
            if in_stock_only and summary.total_stock == 0:
                continue
            if wanted_size and wanted_size not in summary.sizes_in_stock:
                continue
            matches.append((score, summary))

    matches.sort(key=lambda m: (-m[0], m[1].name))
    results = [m[1] for m in matches[:MAX_RESULTS]]
    for r in results:
        ctx.deps.seen_product_ids.add(r.product_id)
        ctx.deps.seen_prices.add(r.price)
        ctx.deps.seen_quantities.add(r.total_stock)
    # Aggregates cover ALL matches, so "N items from $X to $Y" is true even when only 12 are listed.
    all_prices = [m[1].price for m in matches]
    in_stock_matches = sum(1 for m in matches if m[1].total_stock > 0)
    ctx.deps.seen_prices.update(all_prices)
    ctx.deps.seen_quantities.update({len(matches), in_stock_matches})
    ctx.deps.last_total_matches = len(matches)
    return SearchResult(
        total_matches=len(matches),
        price_min=min(all_prices) if all_prices else None,
        price_max=max(all_prices) if all_prices else None,
        price_range_display=(
            None if not all_prices
            else _price_display(min(all_prices)) if min(all_prices) == max(all_prices)
            else f"{_price_display(min(all_prices))}–{_price_display(max(all_prices))}"
        ),
        in_stock_matches=in_stock_matches,
        results=results,
    )


def get_product_info(ctx: RunContext[ShopDeps], product: str) -> ProductInfo | LookupFailed:
    """Get one product's description, colors, garment type, price, and total stock.

    Use for "tell me about…", "what does it look like?", "what color is…?".

    Args:
        product: A product_id (e.g. "basic-hoodie-big-yale") or the product's name.
    """
    _log(ctx, f"get_product_info({product!r})", f"Looking up details for {_pretty(product)}…")
    with closing(connect_ro()) as conn:
        found = _resolve(conn, product)
    if isinstance(found, LookupFailed):
        return found
    ctx.deps.seen_product_ids.add(found["product_id"])
    ctx.deps.seen_prices.add(found["price"])
    ctx.deps.seen_quantities.add(found["total_stock"])
    return ProductInfo(
        product_id=found["product_id"],
        name=found["name"],
        garment_type=found["garment_type"],
        description=found["description"],
        colors=found["colors"],
        price=found["price"],
        price_display=_price_display(found["price"]),
        total_stock=found["total_stock"],
    )


def get_price(ctx: RunContext[ShopDeps], product: str) -> PriceInfo | LookupFailed:
    """Get the exact price of one product from the catalogue. Call this for every price question.

    Args:
        product: A product_id (e.g. "basic-hoodie-big-yale") or the product's name.
    """
    _log(ctx, f"get_price({product!r})", f"Checking the price of {_pretty(product)}…")
    with closing(connect_ro()) as conn:
        found = _resolve(conn, product)
    if isinstance(found, LookupFailed):
        return found
    ctx.deps.seen_product_ids.add(found["product_id"])
    ctx.deps.seen_prices.add(found["price"])
    return PriceInfo(
        product_id=found["product_id"],
        name=found["name"],
        price=found["price"],
        price_display=_price_display(found["price"]),
    )


def check_stock(ctx: RunContext[ShopDeps], product: str, size: str | None = None) -> StockReport | LookupFailed:
    """Get LIVE stock for one product: the exact quantity for every size, read from the inventory table now.

    Call this for every "is it in stock?", "do you have it in M?", "how many are left?" question,
    even if an earlier message or search result mentioned stock. A size with quantity 0 is SOLD OUT.

    Args:
        product: A product_id (e.g. "basic-hoodie-big-yale") or the product's name.
        size: The size the shopper asked about, if any (XS, S, M, L, XL, XXL, or words like "medium").
    """
    _log(ctx, f"check_stock({product!r}, size={size!r})", f"Checking live stock for {_pretty(product)}" + (f" ({size})" if size else "") + "…")
    wanted = normalize_size(size) if size else None
    if size and not wanted:
        return LookupFailed(error=f"Unknown size {size!r}. Sizes are {', '.join(SIZE_ORDER)}.")
    with closing(connect_ro()) as conn:
        found = _resolve(conn, product)
    if isinstance(found, LookupFailed):
        return found

    lines = [SizeStockLine(size=i["size"], quantity=i["quantity"], status=_status(i["quantity"])) for i in found["inventory"]]
    by_size = {line.size: line for line in lines}
    in_stock = [line.size for line in lines if line.quantity > 0]
    sold_out = [line.size for line in lines if line.quantity == 0]
    requested = by_size.get(wanted) if wanted else None

    # Plain-English summary, so the model has the exact sentence to base its answer on.
    parts = []
    if requested:
        if requested.status == "sold_out":
            parts.append(f"Size {wanted} is SOLD OUT (0 left).")
        elif requested.status == "low_stock":
            parts.append(f"Size {wanted} is low: only {requested.quantity} left.")
        else:
            parts.append(f"Size {wanted} is in stock ({requested.quantity} available).")
    parts.append(
        "In stock: " + ", ".join(f"{s} ({by_size[s].quantity})" for s in in_stock) + "."
        if in_stock
        else "Every size is SOLD OUT."
    )
    if sold_out and in_stock:
        parts.append("Sold out: " + ", ".join(sold_out) + ".")

    ctx.deps.seen_product_ids.add(found["product_id"])
    ctx.deps.seen_quantities.update(line.quantity for line in lines)
    ctx.deps.seen_quantities.add(found["total_stock"])
    if requested and requested.status == "sold_out":
        ctx.deps.sold_out_requests.append((found["name"], wanted))

    return StockReport(
        product_id=found["product_id"],
        name=found["name"],
        requested_size=wanted,
        requested_size_quantity=requested.quantity if requested else None,
        requested_size_status=requested.status if requested else None,
        sizes=lines,
        total_stock=found["total_stock"],
        sizes_in_stock=in_stock,
        sizes_sold_out=sold_out,
        summary=" ".join(parts),
        checked_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )


def get_customer_profile(ctx: RunContext[ShopDeps]) -> CustomerContext | str:
    """Get the logged-in shopper's account details: first name, last name, email, and customer-since date.

    Use when they ask about their account ("what email am I signed in with?") or you need their name.
    """
    _log(ctx, "get_customer_profile()", "Pulling up your account…")
    return ctx.deps.customer or "The shopper is a guest (not logged in). There is no account to look up."


def get_current_page(ctx: RunContext[ShopDeps]) -> ProductInfo | PageContext | str:
    """Get what the shopper is looking at right now.

    On a product page this returns that product's full info (description, colors, price, total stock),
    so "do you have this in pink?" or "how much is this?" can be answered. Otherwise it returns the page and
    any Products-page search or category filter.
    """
    _log(ctx, "get_current_page()", "Looking at the item on your screen…")
    if ctx.deps.viewed_product:
        return get_product_info(ctx, ctx.deps.viewed_product.product_id)
    return ctx.deps.page or "No page context was sent."


# ---------- restock alerts (the only tools that write, and only to restock_alerts for this shopper) ----------

def _alert_target(ctx: RunContext[ShopDeps], product: str, size: str) -> tuple[dict, str] | RestockAlertResult:
    if ctx.deps.customer is None:
        return RestockAlertResult(
            ok=False, status="guest",
            message="Restock alerts need an account. Ask the shopper to log in or create one, then try again.",
        )
    wanted = normalize_size(size)
    if not wanted:
        return RestockAlertResult(ok=False, status="error", message=f"Unknown size {size!r}. Sizes are {', '.join(SIZE_ORDER)}.")
    with closing(connect_ro()) as conn:
        found = _resolve(conn, product)
    if isinstance(found, LookupFailed):
        return RestockAlertResult(ok=False, status="error", message=found.error)
    return found, wanted


def create_restock_alert(ctx: RunContext[ShopDeps], product: str, size: str) -> RestockAlertResult:
    """Save a restock alert so the shopper is told when a SOLD-OUT size is back.

    Only call this after the shopper says yes to an alert (for example "yes, notify me"). Works only for
    logged-in shoppers, and only for a size that check_stock shows as sold out right now.

    Args:
        product: A product_id or product name.
        size: The sold-out size (XS, S, M, L, XL, XXL, or words like "medium").
    """
    _log(ctx, f"create_restock_alert({product!r}, {size!r})", f"Setting a restock alert for {_pretty(product)} ({size})…")
    target = _alert_target(ctx, product, size)
    if isinstance(target, RestockAlertResult):
        return target
    found, wanted = target
    quantity = next((i["quantity"] for i in found["inventory"] if i["size"] == wanted), 0)
    ctx.deps.seen_product_ids.add(found["product_id"])
    if quantity > 0:
        ctx.deps.seen_quantities.add(quantity)
        return RestockAlertResult(
            ok=False, status="in_stock",
            message=f"No alert needed: {found['name']} is in stock in {wanted} ({quantity} available).",
        )
    status, alert = create_alert(ctx.deps.customer.user_id, found["product_id"], wanted)
    if status == "limit":
        return RestockAlertResult(
            ok=False, status="limit",
            message=f"The shopper already has {MAX_ACTIVE_ALERTS} active alerts. They can cancel one first.",
        )
    ctx.deps.alerts_created.append(alert)
    return RestockAlertResult(
        ok=True, status=status, alert=alert,
        message=(
            f"Alert {'already set' if status == 'already_exists' else 'saved'}: {found['name']} in {wanted}. "
            "The shopper will see a notice in this chat when it's back in stock. Don't promise a restock date."
        ),
    )


def list_restock_alerts(ctx: RunContext[ShopDeps]) -> RestockAlertList | RestockAlertResult:
    """List the logged-in shopper's active restock alerts, with live stock for each (back_in_stock = true means it's back)."""
    _log(ctx, "list_restock_alerts()", "Checking your restock alerts…")
    if ctx.deps.customer is None:
        return RestockAlertResult(ok=False, status="guest", message="Guests don't have restock alerts.")
    alerts = active_alerts(ctx.deps.customer.user_id)
    ctx.deps.alerts_listed.extend(alerts)
    for a in alerts:
        ctx.deps.seen_product_ids.add(a.product_id)
        ctx.deps.seen_quantities.add(a.current_quantity)
    return RestockAlertList(alerts=alerts)


def cancel_restock_alert(ctx: RunContext[ShopDeps], product: str, size: str) -> RestockAlertResult:
    """Cancel one of the logged-in shopper's restock alerts.

    Args:
        product: A product_id or product name.
        size: The size of the alert to cancel.
    """
    _log(ctx, f"cancel_restock_alert({product!r}, {size!r})", f"Cancelling the alert for {_pretty(product)} ({size})…")
    target = _alert_target(ctx, product, size)
    if isinstance(target, RestockAlertResult):
        return target
    found, wanted = target
    if not cancel_alert(ctx.deps.customer.user_id, found["product_id"], wanted):
        return RestockAlertResult(ok=False, status="not_found", message=f"No active alert for {found['name']} in {wanted}.")
    ctx.deps.alerts_cancelled.append(
        RestockAlert(product_id=found["product_id"], name=found["name"], size=wanted, created_at="", current_quantity=0, back_in_stock=False)
    )
    return RestockAlertResult(ok=True, status="cancelled", message=f"Cancelled the alert for {found['name']} in {wanted}.")


def get_store_info(ctx: RunContext[ShopDeps], topic: str) -> str:
    """Get verified Campus Customs store facts.

    Args:
        topic: One of: location, hours, contact, returns, shipping, custom_orders, history, ordering.
    """
    _log(ctx, f"get_store_info({topic!r})", f"Looking up our {topic.replace('_', ' ')} info…")
    key = topic.lower().strip().replace(" ", "_")
    return STORE_INFO.get(key, f"No info on {topic!r}. Available topics: {', '.join(STORE_INFO)}.")


# Every tool is wrapped so each call lands in the audit trail (time, name, short args/result, ms, ok).
SHOP_TOOLS = [
    audited(t)
    for t in (
        search_products, get_product_info, get_price, check_stock,
        get_current_page, get_customer_profile, get_store_info,
        create_restock_alert, list_restock_alerts, cancel_restock_alert,
    )
]
