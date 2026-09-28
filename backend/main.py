"""Campus Customs backend (FastAPI).

Problem 3: serves the product catalogue, per-size inventory, and product images.
Problem 4: accounts (auth.py).
Problem 5: POST /api/chat runs the PydanticAI shop agent (agent.py, tools.py, models.py, prompts/prompt.md).
Problem 8: logged-in chats are saved/reloaded (chat_store.py); page context tells the agent what 'this' is.

Run from the backend folder:
    cd backend
    ../.venv/bin/uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from contextlib import closing

from fastapi import Cookie, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded

import chat_store
from agent import redact_sensitive, run_chat
from auth import init_auth_tables, router as auth_router, user_for_token
from models import MAX_HISTORY_TURNS, ChatHistoryResponse, ChatRequest, ChatResponse, CustomerContext, RestockAlert
from tools import (
    PRODUCTS_DIR,
    active_alerts,
    connect_ro,
    get_product,
    init_restock_table,
    pop_restocked,
    product_from_row,
)

log = logging.getLogger("campus_customs")

app = FastAPI(title="Campus Customs API")

# The Vite dev server proxies /api and /media, but allow direct calls in dev too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
    allow_credentials=True,
)

init_auth_tables()
chat_store.init_chat_tables()
init_restock_table()
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 echoes the submitted input (including passwords); return only a message.
    messages = []
    for err in exc.errors():
        field = str(err["loc"][-1]).replace("_", " ")
        if err["type"] == "string_too_short" and err["ctx"]["min_length"] == 1:
            messages.append(f"{field.capitalize()} is required.")
        elif err["type"] == "string_too_short":
            messages.append(f"{field.capitalize()} must be at least {err['ctx']['min_length']} characters.")
        elif err["type"] == "string_too_long":
            messages.append(f"{field.capitalize()} must be at most {err['ctx']['max_length']} characters.")
        else:
            msg = err["msg"].removeprefix("Value error, ")
            messages.append(msg if msg.endswith(".") else f"{field.capitalize()}: {msg}.")
    return JSONResponse(status_code=422, content={"detail": " ".join(messages)})


# Product photos live in data/products/<product_id>.jpg (never committed).
app.mount("/media/products", StaticFiles(directory=PRODUCTS_DIR), name="product-images")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/products")
def list_products(
    q: str | None = Query(None, description="Search name, type, description, colors, tags"),
    garment_type: str | None = Query(None, description="Case-insensitive substring match"),
) -> list[dict]:
    sql = """
        SELECT c.*, COALESCE(SUM(i.quantity), 0) AS total_stock
        FROM catalogue c LEFT JOIN inventory i ON i.product_id = c.product_id
    """
    where, params = [], []
    if q:
        where.append(
            "(c.name LIKE ? OR c.garment_type LIKE ? OR c.description LIKE ?"
            " OR c.colors LIKE ? OR c.search_tags LIKE ?)"
        )
        params += [f"%{q}%"] * 5
    if garment_type:
        where.append("c.garment_type LIKE ?")
        params.append(f"%{garment_type}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY c.product_id ORDER BY c.name"

    with closing(connect_ro()) as conn:
        return [product_from_row(r) for r in conn.execute(sql, params).fetchall()]


@app.get("/api/products/{product_id}")
def product_detail(product_id: str) -> dict:
    with closing(connect_ro()) as conn:
        product = get_product(conn, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def current_customer(cc_session: str | None) -> CustomerContext | None:
    user = user_for_token(cc_session)
    return CustomerContext(**user) if user else None


def sanitize(body: ChatRequest) -> tuple[ChatRequest, list[str]]:
    """Strip card numbers / SSNs from the new message (and guest history) before anything stores or reads them."""
    message, found = redact_sensitive(body.message)
    history = [t.model_copy(update={"content": redact_sensitive(t.content)[0]}) for t in body.history]
    return body.model_copy(update={"message": message, "history": history}), found


async def answer(
    body: ChatRequest, customer: CustomerContext | None, on_status: Callable[[str], None] | None = None
) -> ChatResponse:
    # Logged in: history comes from the database (can't be forged by the browser). Guest: from the browser.
    body, redactions = sanitize(body)
    history = chat_store.load_turns(customer.user_id, MAX_HISTORY_TURNS) if customer else body.history
    try:
        return await run_chat(body.message, history, customer, body.page, on_status, redactions)
    except ModelHTTPError as exc:
        # The model provider's content filter blocks jailbreak/abusive prompts before the agent sees them.
        if "content_filter" in str(exc.body):
            log.warning("chat blocked by provider content filter")
            return ChatResponse(
                reply="I can only help with Campus Customs gear, sizes, stock, and store policies. What can I help you find?"
            )
        log.exception("model request failed")
        raise HTTPException(502, "The shop assistant is having trouble right now. Please try again in a moment.")
    except UnexpectedModelBehavior:
        # The double-check validator rejected every retry: never send an unverified price/stock answer.
        log.warning("chat reply failed double-check after retries")
        return ChatResponse(
            reply="I want to be sure I give you exact prices and stock, and I couldn't confirm them just now. "
            "Could you ask about one item at a time?"
        )
    except UsageLimitExceeded:
        log.warning("chat hit usage limits")
        return ChatResponse(
            reply="That one took me too many steps to look up. Could you ask in a simpler way, like one item at a time?"
        )
    except Exception:
        log.exception("chat failed")
        raise HTTPException(502, "The shop assistant is having trouble right now. Please try again in a moment.")


@app.post("/api/chat")
async def chat(body: ChatRequest, cc_session: str | None = Cookie(None)) -> ChatResponse:
    """Website chat widget -> shop agent. Guests can chat; logged-in shoppers' chats are saved and reloaded."""
    customer = current_customer(cc_session)
    response = await answer(body, customer)
    if customer:
        chat_store.save_exchange(customer.user_id, redact_sensitive(body.message)[0], response)
    return response


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, cc_session: str | None = Cookie(None)) -> StreamingResponse:
    """Same as /api/chat, but streams progress (Server-Sent Events) while the agent works.

    Events: `status` {"text"} for each step, then exactly one `done` (ChatResponse) or `error` {"detail"}.
    Only progress is streamed, never unverified answer text: `done` arrives after the double-check.
    """
    customer = current_customer(cc_session)
    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
    started = time.perf_counter()

    def on_status(text: str) -> None:
        queue.put_nowait(("status", {"text": text, "t": round(time.perf_counter() - started, 2)}))

    async def run() -> None:
        try:
            response = await answer(body, customer, on_status)
            if customer:
                chat_store.save_exchange(customer.user_id, redact_sensitive(body.message)[0], response)
            queue.put_nowait(("done", response.model_dump()))
        except HTTPException as exc:
            queue.put_nowait(("error", {"detail": exc.detail}))
        except Exception:
            log.exception("chat stream failed")
            queue.put_nowait(("error", {"detail": "The shop assistant is having trouble right now. Please try again."}))

    task = asyncio.create_task(run())

    async def events():
        yield _sse("status", {"text": "Reading your question…", "t": 0})
        try:
            while True:
                event, data = await queue.get()
                yield _sse(event, data)
                if event in ("done", "error"):
                    break
        finally:
            if not task.done():  # shopper closed the tab: stop paying for the model call
                task.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/chat/history")
def chat_history(cc_session: str | None = Cookie(None)) -> ChatHistoryResponse:
    """The logged-in shopper's saved chat (only ever their own). Guests get an empty list."""
    customer = current_customer(cc_session)
    if not customer:
        return ChatHistoryResponse(logged_in=False)
    return ChatHistoryResponse(
        logged_in=True,
        messages=chat_store.load_history(customer.user_id),
        restocked=pop_restocked(customer.user_id),  # in-app "it's back!" notice, shown once
    )


@app.get("/api/restock-alerts")
def my_restock_alerts(cc_session: str | None = Cookie(None)) -> list[RestockAlert]:
    """The logged-in shopper's active alerts (product pages mark those sizes 'Alert set'). Guests: []."""
    customer = current_customer(cc_session)
    return active_alerts(customer.user_id) if customer else []


@app.delete("/api/chat/history")
def clear_chat_history(cc_session: str | None = Cookie(None)) -> dict:
    customer = current_customer(cc_session)
    if not customer:
        raise HTTPException(401, "Log in to manage your saved chat.")
    return {"deleted": chat_store.clear_history(customer.user_id)}
