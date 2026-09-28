"""Campus Customs shop chatbot: one PydanticAI agent, wired to OpenAI through Portkey.

- System prompt: backend/prompts/prompt.md (read at startup)
- Tools:         backend/tools.py (read-only search, product info, price, stock, store info)
- Types:         backend/models.py
- Model:         gpt-5.6-luna by default; CHAT_MODEL may pick another allow-listed 5.6/6-series model
"""

import asyncio
import logging
import os
import re
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, UsageLimits
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

import db
from models import (
    MAX_HISTORY_TURNS,
    ChatResponse,
    ChatTurn,
    CustomerContext,
    PageContext,
    ProductCard,
    ShopDeps,
    ShopReply,
    ViewedProduct,
)
from tools import SHOP_TOOLS, SIZE_ALIASES, audit_append, audit_now, audit_short, new_run_id

# ---------- safety guards (back up the rules in prompts/prompt.md) ----------
# redact_sensitive(): strips card numbers (Luhn-checked) and SSNs from shopper messages BEFORE the model,
# the chat history table, or the audit trail see them. allowed_emails(): the only emails a reply may contain.

STORE_EMAIL = "orderdept@campuscustoms.com"
_CARD_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
        alt = not alt
    return total % 10 == 0


def redact_sensitive(text: str) -> tuple[str, list[str]]:
    """Returns (cleaned text, kinds removed). Shoppers should never share these in a shop chat."""
    found: list[str] = []

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            found.append("card number")
            return "[card number removed]"
        return m.group(0)

    text = _CARD_RE.sub(card, text)
    if _SSN_RE.search(text):
        found.append("social security number")
        text = _SSN_RE.sub("[SSN removed]", text)
    return text, found


def allowed_emails(customer_email: str | None) -> set[str]:
    return {STORE_EMAIL} | ({customer_email.lower()} if customer_email else set())


BACKEND_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BACKEND_DIR / "prompts" / "prompt.md"

# PORTKEY_API_KEY lives in the course-root .env (two levels up); an hw4/.env also works.
load_dotenv(db.ROOT / ".env")
load_dotenv(db.ROOT.parent / ".env")

ALLOWED_MODELS = {"gpt-5.6-luna", "gpt-6-astra"}
DEFAULT_MODEL = "gpt-5.6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# Cost/loop guardrails per chat message.
log = logging.getLogger("uvicorn.error")

USAGE_LIMITS = UsageLimits(request_limit=8, tool_calls_limit=10, total_tokens_limit=60_000)


def build_model() -> OpenAIResponsesModel:
    model_name = os.getenv("CHAT_MODEL", DEFAULT_MODEL)
    if model_name not in ALLOWED_MODELS:
        raise RuntimeError(f"CHAT_MODEL={model_name!r} is not allowed. Use one of {sorted(ALLOWED_MODELS)}.")
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to the .env file in the course folder.")
    client = AsyncOpenAI(
        base_url=PORTKEY_BASE_URL,
        api_key=api_key,
        default_headers={"x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(model_name, provider=OpenAIProvider(openai_client=client))


MODEL_NAME = os.getenv("CHAT_MODEL", DEFAULT_MODEL)

shop_agent = Agent(
    build_model(),
    deps_type=ShopDeps,
    output_type=ShopReply,
    instructions=PROMPT_PATH.read_text(encoding="utf-8"),
    tools=SHOP_TOOLS,
    retries=2,
    name="campus_customs_shop_assistant",
)


@shop_agent.instructions
def customer_context(ctx: RunContext[ShopDeps]) -> str:
    """Who is chatting. Built per request from ShopDeps.customer (loaded from the session cookie)."""
    c = ctx.deps.customer
    if c is None:
        return (
            "## Who you're talking to\nA guest (not logged in). Their chat is not saved between visits. "
            "If they want you to remember them, they can create an account or log in."
        )
    return (
        "## Who you're talking to\n"
        f"Logged-in customer: {c.first_name} {c.last_name}, email {c.email}, customer since {c.member_since[:10]}.\n"
        "Their chat history is saved, so earlier messages in this conversation may be from previous visits.\n"
        "Use their first name now and then. Mention their email only if they ask about their account."
    )


@shop_agent.instructions
def redaction_notice(ctx: RunContext[ShopDeps]) -> str:
    if not ctx.deps.redactions:
        return ""
    kinds = " and ".join(ctx.deps.redactions)
    return (
        f"## Safety notice\nThe shopper's message contained a {kinds}, which was removed before you saw it. "
        "Briefly remind them never to share payment or ID details in chat (you can't take payments), then help "
        "with the rest of their question."
    )


@shop_agent.instructions
def page_context(ctx: RunContext[ShopDeps]) -> str:
    """What the shopper is looking at, so 'this' / 'it' / 'this one' resolve to the right product."""
    page, viewed = ctx.deps.page, ctx.deps.viewed_product
    if viewed:
        return (
            "## Current page\n"
            f"The shopper is on the product page for **{viewed.name}** (product_id `{viewed.product_id}`, "
            f"{viewed.garment_type}, colors: {', '.join(viewed.colors)}).\n"
            "If they say 'this', 'it', 'this one', or ask about a color or size without naming a product, "
            "they mean this item. Look it up with its product_id."
        )
    if page and page.page_type == "products":
        filters = [f"search '{page.search_query}'" if page.search_query else "", f"category '{page.category}'" if page.category else ""]
        active = " and ".join(f for f in filters if f)
        return f"## Current page\nThe shopper is browsing the Products page{' filtered by ' + active if active else ''}."
    if page:
        return f"## Current page\nThe shopper is on the {page.page_type.replace('-', ' ')} page ({page.path})."
    return ""


PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)")
QUANTITY_RES = [
    re.compile(r"\b(\d+)\s+(?:units?\s+|pieces?\s+)?(?:left|in stock|available|remaining)\b", re.I),
    re.compile(r"\bonly\s+(\d+)\b", re.I),
    re.compile(r"\b(?:XXL|XL|XS|S|M|L)\s*\((\d+)\)"),
    re.compile(r"\b(?:XXL|XL|XS|S|M|L)\s*[:=\-\u2013\u2014]\s*(\d+)\b"),
]
SOLD_OUT_RE = re.compile(r"sold out|out of stock", re.I)
ALERT_CLAIM_RE = re.compile(
    r"\b(alert (is |has been )?(set|saved|created)|(i'?ve|i have) (set|saved|added)|on the (restock|wait) ?list|"
    r"(we'?ll|i'?ll|we will|i will) (notify|let you know|tell you|alert you))",
    re.I,
)
ALERT_CANCEL_RE = re.compile(r"\b(alert (is |has been )?(cancel+ed|removed|deleted)|(i'?ve|i have) (cancel+ed|removed))", re.I)


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def _mentions_size(text: str, size: str) -> bool:
    words = [size] + [alias for alias, code in SIZE_ALIASES.items() if code == size]
    return any(re.search(rf"\b{re.escape(w)}\b", text, re.I) for w in words)


def _retry(deps: ShopDeps, reason: str) -> ModelRetry:
    """Record a double-check rejection in the audit trail, then send the model back to fix it."""
    deps.audit_events.append({"t": audit_now(), "type": "double_check_retry", "reason": audit_short(reason)})
    return ModelRetry(reason)


@shop_agent.output_validator
def double_check_reply(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
    """Double-check the reply against what the tools actually returned before the shopper sees it."""
    deps, reply = ctx.deps, output.reply
    if deps.on_status and not deps.double_checked:
        deps.on_status("Double-checking prices and stock…")
        deps.double_checked = True
    if not reply.strip():
        raise _retry(deps, "Your reply was empty. Write a short answer for the shopper.")

    # 1. Cards may only show products a tool returned this turn.
    unknown = [pid for pid in output.product_ids if pid not in deps.seen_product_ids]
    if unknown:
        raise _retry(deps,
            f"These product_ids were not returned by a tool this turn: {unknown}. "
            "Look them up with search_products / get_product_info first, or remove them."
        )

    # 2. Every $ amount must be a price a tool returned (or a number the shopper typed, e.g. "under $70").
    allowed_prices = deps.seen_prices | _numbers(deps.user_message)
    bad_prices = [m for m in PRICE_RE.findall(reply) if float(m.replace(",", "")) not in allowed_prices]
    if bad_prices:
        raise _retry(deps,
            f"Your reply mentions ${', $'.join(bad_prices)}, but no tool returned that price this turn. "
            "Call get_price for each product you quote and use its exact price."
        )

    # 3. Every stock count ("8 left", "only 3", "S (12)") must be a quantity a tool returned this turn.
    allowed_qty = {float(q) for q in deps.seen_quantities} | _numbers(deps.user_message)
    bad_qty = [m for rx in QUANTITY_RES for m in rx.findall(reply) if float(m) not in allowed_qty]
    if bad_qty:
        raise _retry(deps,
            f"Your reply states stock count(s) {bad_qty} that no tool returned this turn. "
            "Call check_stock and quote its exact quantities."
        )

    # 4. Never claim a restock alert was set (or cancelled) unless the tool actually did it this turn.
    if ALERT_CLAIM_RE.search(reply) and not (deps.alerts_created or deps.alerts_listed):
        raise _retry(deps,
            "Your reply says an alert or notification is set, but no tool saved or found one this turn. "
            "Either call create_restock_alert (only if the shopper asked for it and the size is sold out) "
            "or don't claim it."
        )
    if ALERT_CANCEL_RE.search(reply) and not deps.alerts_cancelled:
        raise _retry(deps, "Your reply says an alert was cancelled, but cancel_restock_alert did not cancel one this turn.")

    # 5. Privacy: the only email addresses a reply may contain are the store's and the shopper's own.
    allowed = allowed_emails(deps.customer.email if deps.customer else None)
    leaked = [e for e in EMAIL_RE.findall(reply) if e.lower().rstrip(".") not in allowed]
    if leaked:
        raise _retry(deps, "Your reply contains an email address you may not share. Remove it; only "
                     "orderdept@campuscustoms.com (or the logged-in shopper's own email, if they asked) is allowed.")

    # 6. If the shopper asked about a size that is sold out, the reply must say so clearly.
    for name, size in deps.sold_out_requests:
        if not (SOLD_OUT_RE.search(reply) and _mentions_size(reply, size)):
            raise _retry(deps,
                f"check_stock shows {name} is SOLD OUT in size {size}. "
                f"Say clearly that size {size} is sold out, then offer the sizes that are in stock."
            )
    return output


def to_model_history(history: list[ChatTurn]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            text = turn.content
            if turn.product_ids:
                text += "\n\n[Product cards shown, in order: " + ", ".join(turn.product_ids) + "]"
            messages.append(ModelResponse(parts=[TextPart(content=text)]))
    return messages


def product_cards(product_ids: list[str]) -> list[ProductCard]:
    """Rebuild cards from the DB so price/stock on screen are always the real numbers."""
    cards = []
    with closing(db.connect_ro()) as conn:
        for pid in dict.fromkeys(product_ids):  # de-dupe, keep order
            product = db.get_product(conn, pid)
            if product:
                cards.append(ProductCard(**product))
    return cards


def resolve_viewed_product(page: PageContext | None) -> ViewedProduct | None:
    """Trust only product ids that exist in the catalogue; the browser could send anything."""
    if not page or not page.product_id:
        return None
    with closing(db.connect_ro()) as conn:
        product = db.get_product(conn, page.product_id)
    if not product:
        return None
    return ViewedProduct(
        product_id=product["product_id"], name=product["name"],
        garment_type=product["garment_type"], colors=product["colors"],
    )


def _stop_reason(exc: BaseException | None) -> str:
    if exc is None:
        return "final_answer"
    if isinstance(exc, UnexpectedModelBehavior):
        return "double_check_failed"  # validator rejected every retry; main.py sends a safe fallback
    if isinstance(exc, UsageLimitExceeded):
        return "usage_limit"
    if isinstance(exc, ModelHTTPError):
        return "content_filter" if "content_filter" in str(exc.body) else "model_error"
    if isinstance(exc, asyncio.CancelledError):
        return "cancelled"  # shopper closed the stream
    return "error"


async def run_chat(
    message: str,
    history: list[ChatTurn],
    customer: CustomerContext | None = None,
    page: PageContext | None = None,
    on_status: Callable[[str], None] | None = None,
    redactions: list[str] | None = None,
) -> ChatResponse:
    deps = ShopDeps(
        customer=customer, page=page, viewed_product=resolve_viewed_product(page),
        user_message=message, on_status=on_status, redactions=redactions or [],
    )
    run_id, started_at, t0 = new_run_id(), audit_now(), time.perf_counter()
    result, response, error = None, None, None
    try:
        result = await shop_agent.run(
            message,
            deps=deps,
            message_history=to_model_history(history),
            usage_limits=USAGE_LIMITS,
        )
        output = result.output
        cards = product_cards(output.product_ids)
        response = ChatResponse(
            reply=output.reply,
            products=cards,
            results_title=(output.results_title or "From your chat") if cards else None,
            search_query=output.search_query if cards else None,
            # Only a browse-style answer (several cards) gets "N of M"; a single-item answer is just that item.
            total_matches=max(deps.last_total_matches, len(cards)) if len(cards) > 1 and deps.last_total_matches else None,
            alerts_created=deps.alerts_created,
        )
        return response
    except BaseException as exc:
        error = exc
        raise
    finally:
        usage = result.usage if result else None
        audit_append({
            "run_id": run_id,
            "started_at": started_at,
            "ended_at": audit_now(),
            "duration_ms": round((time.perf_counter() - t0) * 1000),
            "model": MODEL_NAME,
            "endpoint": "/api/chat/stream" if on_status else "/api/chat",
            "user": f"user_id={customer.user_id}" if customer else "guest",  # never the email
            "page": page.path if page else None,
            # Shopper text is never stored in the audit trail (privacy); only its length and what was stripped.
            "message": f"[redacted shopper message, {len(message)} chars]",
            "redactions": deps.redactions,
            "history_turns": min(len(history), MAX_HISTORY_TURNS),
            "events": deps.audit_events,
            "tool_calls": sum(1 for e in deps.audit_events if e["type"] == "tool_call"),
            "double_check_retries": sum(1 for e in deps.audit_events if e["type"] == "double_check_retry"),
            "usage": {
                "model_requests": usage.requests, "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            } if usage else None,
            "stop_reason": _stop_reason(error),
            "error": audit_short(f"{type(error).__name__}: {error}") if error else None,
            "reply": audit_short(response.reply) if response else None,
            "product_ids": [c.product_id for c in response.products] if response else [],
            "alerts_created": [f"{a.product_id}:{a.size}" for a in deps.alerts_created],
        })
        log.info("chat run=%s stop=%s tools=%s", run_id, _stop_reason(error), deps.tool_calls)
