"""Pydantic / PydanticAI types for the Campus Customs shop chatbot."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 1000
MAX_HISTORY_TURNS = 20
MAX_PAGE_RESULTS = 12  # product cards per answer; also the cap on product_ids in history turns


# ---------- chat API (website <-> FastAPI) ----------

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)
    # product_ids shown as cards with an assistant turn, so follow-ups like "the first one" resolve.
    product_ids: list[str] = Field(default_factory=list, max_length=MAX_PAGE_RESULTS)


PageType = Literal["home", "products", "product", "about", "login", "create-account", "other"]


class PageContext(BaseModel):
    """Where the shopper is on the site when they send a message (sent by the browser)."""

    path: str = Field(default="/", max_length=200)
    page_type: PageType = "other"
    product_id: str | None = Field(default=None, max_length=120, description="Set on a product detail page.")
    search_query: str | None = Field(default=None, max_length=100, description="Products page search box.")
    category: str | None = Field(default=None, max_length=40, description="Products page category chip.")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    # Prior turns, oldest first, for GUESTS. Logged-in shoppers' history is loaded from the database instead.
    history: list[ChatTurn] = Field(default_factory=list, max_length=100)
    page: PageContext | None = None


class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductCard(BaseModel):
    """A product the chat shows on the page. Always rebuilt from the DB, never from model text."""

    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    colors: list[str]
    image_url: str
    total_stock: int
    inventory: list[SizeStock]


class ChatResponse(BaseModel):
    """API contract for POST /api/chat. The frontend renders `products` as a grid on the page."""

    reply: str
    products: list[ProductCard] = Field(default_factory=list)
    # Heading for the on-page results grid, e.g. "Navy hoodies under $70". None when products is empty.
    results_title: str | None = None
    # Catalogue keywords for a "See all in the shop" link (/products?q=...), when more items match than are shown.
    search_query: str | None = None
    # How many catalogue items matched the agent's last search (can be more than len(products)).
    total_matches: int | None = None
    # Restock alerts saved this turn, shown as confirmation chips in the chat.
    alerts_created: list["RestockAlert"] = Field(default_factory=list)


class HistoryMessage(BaseModel):
    """One saved message, as returned by GET /api/chat/history (cards rebuilt from live data)."""

    role: Literal["user", "assistant"]
    content: str
    created_at: str
    products: list[ProductCard] = Field(default_factory=list)
    results_title: str | None = None
    search_query: str | None = None
    total_matches: int | None = None


class ChatHistoryResponse(BaseModel):
    logged_in: bool
    messages: list[HistoryMessage] = Field(default_factory=list)
    # Alerted sizes that are back in stock since last visit (each is returned once, then marked notified).
    restocked: list["RestockAlert"] = Field(default_factory=list)


# ---------- who is chatting + what page they are on (agent context) ----------

class CustomerContext(BaseModel):
    """The logged-in shopper, loaded server-side from the session cookie. Never includes the password hash."""

    user_id: int
    first_name: str
    last_name: str
    email: str
    member_since: str


class ViewedProduct(BaseModel):
    """The product on the page the shopper is looking at, resolved from PageContext.product_id."""

    product_id: str
    name: str
    garment_type: str
    colors: list[str]


# ---------- agent output + dependencies ----------

class ShopReply(BaseModel):
    """What the agent must return every turn."""

    reply: str = Field(
        description=(
            "Your message to the shopper, in the Campus Customs voice. Short markdown is fine "
            "(bold, bullet lists). Every price, size, and stock number must come from a tool result."
        )
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=MAX_PAGE_RESULTS,
        description=(
            "product_id values (from tool results this turn) to show as product cards ON THE WEBSITE PAGE, "
            "most relevant first. For 'what X do you have?' include every search result (up to 12). "
            "For a question about one item, just that item. Empty if nothing fits."
        ),
    )
    results_title: str | None = Field(
        default=None,
        max_length=60,
        description="Short heading for the on-page product grid, e.g. 'Hoodies', 'Gray crewnecks in M'. Required when product_ids is not empty.",
    )
    search_query: str | None = Field(
        default=None,
        max_length=40,
        description="1-2 catalogue keywords for a 'See all' link when there are more matches than cards, e.g. 'hoodie', 'hockey'.",
    )


# ---------- tool return types (what the agent sees from the database) ----------

StockStatus = Literal["in_stock", "low_stock", "sold_out"]
LOW_STOCK_THRESHOLD = 5  # 1-5 units = "low_stock"; matches the product page labels


class ProductMatch(BaseModel):
    """A candidate when a product name is ambiguous or misspelled."""

    product_id: str
    name: str


class LookupFailed(BaseModel):
    """Returned instead of data when a lookup fails, so the agent never has to guess."""

    error: str
    did_you_mean: list[ProductMatch] = Field(default_factory=list)


class ProductSummary(BaseModel):
    """One row of search results: enough to recommend, not enough to quote exact per-size stock."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    total_stock: int
    sizes_in_stock: list[str]
    sizes_sold_out: list[str]


class SearchResult(BaseModel):
    total_matches: int = Field(description="How many catalogue items matched in total (results holds at most 12).")
    price_min: float | None = Field(description="Lowest price across ALL matches, not just the results shown.")
    price_max: float | None = Field(description="Highest price across ALL matches, not just the results shown.")
    price_range_display: str | None = Field(description="Quote this for the price range, e.g. '$45.00–$88.00' or '$68.00'.")
    in_stock_matches: int = Field(description="How many of ALL matches have at least one size in stock.")
    results: list[ProductSummary]


class ProductInfo(BaseModel):
    """get_product_info: the descriptive facts about one product."""

    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    price: float
    price_display: str
    total_stock: int


class PriceInfo(BaseModel):
    """get_price: just the price, straight from catalogue.price."""

    product_id: str
    name: str
    price: float
    price_display: str
    currency: Literal["USD"] = "USD"


class SizeStockLine(BaseModel):
    size: str
    quantity: int
    status: StockStatus


class StockReport(BaseModel):
    """check_stock: live per-size inventory for one product, read at call time."""

    product_id: str
    name: str
    requested_size: str | None = Field(description="Normalized size the shopper asked about (XS-XXL), if any.")
    requested_size_quantity: int | None
    requested_size_status: StockStatus | None
    sizes: list[SizeStockLine] = Field(description="Every size XS-XXL with its exact quantity and status.")
    total_stock: int
    sizes_in_stock: list[str]
    sizes_sold_out: list[str]
    summary: str = Field(description="Plain-English stock sentence to base your answer on.")
    checked_at: str = Field(description="UTC time the database was read.")


class RestockAlert(BaseModel):
    """A shopper's request to hear when a sold-out size is back (table restock_alerts)."""

    product_id: str
    name: str
    size: str
    created_at: str
    current_quantity: int = Field(description="Live stock for that size right now.")
    back_in_stock: bool


class RestockAlertResult(BaseModel):
    """create_restock_alert / cancel_restock_alert outcome. Only claim success when ok is true."""

    ok: bool
    status: Literal["created", "already_exists", "cancelled", "not_found", "in_stock", "guest", "limit", "error"]
    message: str
    alert: RestockAlert | None = None


class RestockAlertList(BaseModel):
    alerts: list[RestockAlert]


@dataclass
class ShopDeps:
    """Per-request context passed to every tool, and checked by the output validator."""

    customer: CustomerContext | None = None  # None = guest
    page: PageContext | None = None
    viewed_product: ViewedProduct | None = None  # set when page.product_id is a real product
    user_message: str = ""
    # Every product_id a tool returned this run; the output check only allows these on cards.
    seen_product_ids: set[str] = field(default_factory=set)
    # Every price / quantity a tool returned this run; any $ amount or stock count in the reply must be one of these.
    seen_prices: set[float] = field(default_factory=set)
    seen_quantities: set[int] = field(default_factory=set)
    # (product name, size) pairs the shopper asked about that check_stock found SOLD OUT.
    sold_out_requests: list[tuple[str, str]] = field(default_factory=list)
    # total_matches from the most recent search_products call, sent to the page as "N items".
    last_total_matches: int | None = None
    tool_calls: list[str] = field(default_factory=list)
    # Streaming: called with a plain-English progress line ("Checking live stock…"). None for /api/chat.
    on_status: Callable[[str], None] | None = None
    double_checked: bool = False
    # Restock alerts the tools actually saved / cancelled this turn (the reply may only claim these).
    alerts_created: list["RestockAlert"] = field(default_factory=list)
    alerts_cancelled: list["RestockAlert"] = field(default_factory=list)
    alerts_listed: list["RestockAlert"] = field(default_factory=list)  # existing alerts seen via list_restock_alerts
    # Audit trail (tools.audit_append): one event per tool call / double-check retry, written after the run.
    audit_events: list[dict] = field(default_factory=list)
    # Sensitive data removed from the shopper's message before the model saw it (e.g. ["card number"]).
    redactions: list[str] = field(default_factory=list)


ChatResponse.model_rebuild()
ChatHistoryResponse.model_rebuild()
