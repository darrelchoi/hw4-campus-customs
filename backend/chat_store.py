"""Saved chat history for logged-in shoppers (table: chat_messages).

Each exchange stores two rows: the shopper's message and the assistant's reply.
products_json on assistant rows holds *which* products were shown, not their
prices or stock, so reloaded cards are always rebuilt from live data:

    {"product_ids": [...], "results_title": "...", "search_query": "...", "total_matches": 27}

Older seed rows stored a list of full product snapshots; load_* handles both.
"""

import json
from contextlib import closing

import db
from models import MAX_PAGE_RESULTS, ChatResponse, ChatTurn, HistoryMessage, ProductCard

MAX_STORED_CHARS = 4000  # matches ChatTurn.content max_length
HISTORY_PAGE_SIZE = 50  # messages returned to the browser on reload


def init_chat_tables() -> None:
    with closing(db.connect_rw()) as conn, conn:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id, id)")


def _parse_products_json(raw: str | None) -> dict:
    if not raw:
        return {"product_ids": []}
    data = json.loads(raw)
    if isinstance(data, list):  # legacy: list of product snapshots
        return {"product_ids": [p["product_id"] for p in data if isinstance(p, dict) and "product_id" in p]}
    return data


def save_exchange(user_id: int, message: str, response: ChatResponse) -> None:
    meta = None
    if response.products:
        meta = json.dumps(
            {
                "product_ids": [p.product_id for p in response.products],
                "results_title": response.results_title,
                "search_query": response.search_query,
                "total_matches": response.total_matches,
            }
        )
    with closing(db.connect_rw()) as conn, conn:  # one transaction: both rows or neither
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)",
            (user_id, message[:MAX_STORED_CHARS]),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, response.reply[:MAX_STORED_CHARS], meta),
        )


def _recent_rows(conn, user_id: int, limit: int) -> list:
    rows = conn.execute(
        "SELECT role, content, products_json, created_at FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return list(reversed(rows))


def load_turns(user_id: int, limit: int) -> list[ChatTurn]:
    """History for the agent: the server's copy, so a browser cannot forge earlier assistant turns."""
    with closing(db.connect_ro()) as conn:
        rows = _recent_rows(conn, user_id, limit)
    return [
        ChatTurn(
            role=r["role"],
            content=r["content"][:MAX_STORED_CHARS],
            product_ids=_parse_products_json(r["products_json"])["product_ids"][:MAX_PAGE_RESULTS],
        )
        for r in rows
    ]


def load_history(user_id: int, limit: int = HISTORY_PAGE_SIZE) -> list[HistoryMessage]:
    """History for the browser, with product cards rebuilt from the live catalogue and inventory."""
    messages = []
    with closing(db.connect_ro()) as conn:
        for r in _recent_rows(conn, user_id, limit):
            meta = _parse_products_json(r["products_json"])
            cards = []
            for pid in dict.fromkeys(meta["product_ids"][:MAX_PAGE_RESULTS]):
                product = db.get_product(conn, pid)
                if product:  # silently skip products removed from the catalogue
                    cards.append(ProductCard(**product))
            messages.append(
                HistoryMessage(
                    role=r["role"],
                    content=r["content"],
                    created_at=r["created_at"],
                    products=cards,
                    results_title=(meta.get("results_title") or "From your chat") if cards else None,
                    search_query=meta.get("search_query") if cards else None,
                    total_matches=meta.get("total_matches") if cards else None,
                )
            )
    return messages


def clear_history(user_id: int) -> int:
    with closing(db.connect_rw()) as conn, conn:
        return conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,)).rowcount
