"""Tool layer for the Shopping Agent (read-only).

Skeleton: REGISTRY is empty. Person A adds search_products and
categories_brands_list. Person B adds product_get and products_compare.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import AppError
from ai_commerce_marketplace.services import catalog_details, catalog_search

MAX_LIMIT = 20


@dataclass(frozen=True)
class ToolContext:
    """Injected by the router from the token. Not visible to the LLM."""

    session: Session
    customer_id: int | None = None  # None = anonymous visitor


class ToolInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _limit(value: int) -> int:
    if not isinstance(value, int) or value < 1:
        raise ToolInputError("invalid_limit", "limit must be a positive integer")
    return min(value, MAX_LIMIT)


def _jsonable(obj: Any) -> Any:
    """Turn Pydantic models and Decimals into plain JSON-safe values."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_jsonable(v) for v in obj]
    return obj


def _safe(fn: Callable[[], Any]) -> dict[str, Any]:
    """Run a tool body and always return a dict (never raise to the agent)."""
    try:
        return {"ok": True, **_jsonable(fn())}
    except ToolInputError as e:
        return {"ok": False, "error": e.code, "message": str(e)}
    except AppError as e:
        return {"ok": False, "error": e.code, "message": e.message}


def _product_id(value: Any) -> int:
    """Accept 12 or "12"; reject bools, floats, text and non-positive numbers."""
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ToolInputError("invalid_product_id", f"Not a valid product id: {value!r}")
    return value


SORTS = ("newest", "price_asc", "price_desc", "rating")


def _opt_text(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolInputError(f"invalid_{name}", f"{name} must be text")
    return value.strip() or None


def _opt_price(value: Any, name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ToolInputError("invalid_price", f"{name} must be a number")
    try:
        price = Decimal(str(value).strip())
    except InvalidOperation:
        raise ToolInputError("invalid_price", f"{name} must be a number") from None
    if not price.is_finite() or price < 0:
        raise ToolInputError("invalid_price", f"{name} must be 0 or more")
    return price


def _product_ids(values: Any) -> list[int]:
    if not isinstance(values, list | tuple):
        raise ToolInputError("invalid_product_ids", "product_ids must be a list of product ids")
    return [_product_id(v) for v in values]


# ---- tools (Person A) ----
def search_products(
    ctx: ToolContext,
    query: Any = None,
    category: Any = None,
    brand: Any = None,
    min_price: Any = None,
    max_price: Any = None,
    in_stock_only: Any = True,
    sort: Any = "newest",
    sort_spec: Any = None,
    specs: Any = None,
    limit: Any = 5,
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        if sort not in SORTS:
            raise ToolInputError("invalid_sort", f"sort must be one of {list(SORTS)}")
        if not isinstance(in_stock_only, bool):
            raise ToolInputError("invalid_in_stock_only", "in_stock_only must be true or false")
        if specs is not None and not isinstance(specs, dict):
            raise ToolInputError("invalid_specs", "specs must be an object")
        cards = catalog_search.search_products(
            ctx.session,
            query=_opt_text(query, "query"),
            category=_opt_text(category, "category"),
            brand=_opt_text(brand, "brand"),
            min_price=_opt_price(min_price, "min_price"),
            max_price=_opt_price(max_price, "max_price"),
            in_stock_only=in_stock_only,
            sort=sort,
            specs=specs,
            sort_spec=_opt_text(sort_spec, "sort_spec"),
            limit=_limit(limit),
        )
        return {"products": cards, "count": len(cards), "empty": not cards}

    return _safe(run)


# ---- tools (Person B) ----
def product_get(ctx: ToolContext, product_id: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        return {"product": catalog_details.get_product(ctx.session, _product_id(product_id))}

    return _safe(run)


def products_compare(ctx: ToolContext, product_ids: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        return catalog_details.compare_products(ctx.session, _product_ids(product_ids))

    return _safe(run)


def reviews_summary_get(ctx: ToolContext, product_id: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        return catalog_details.reviews_summary(ctx.session, _product_id(product_id))

    return _safe(run)


# What the LLM may fill in. ctx is never listed here.
# Each entry: {"fn": callable, "description": str, "params": [names]}
REGISTRY: dict[str, dict[str, Any]] = {
    "product_get": {
        "fn": product_get,
        "description": (
            "Full details of one product: price, specs, warranty, returnable, stock, rating, "
            "images. in_stock=false means not available now."
        ),
        "params": ["product_id"],
    },
    "products_compare": {
        "fn": products_compare,
        "description": (
            "Compare 2 to 4 products from the same category. Returns each product's details, "
            "the spec_keys to compare on, and missing_ids for ids that do not exist."
        ),
        "params": ["product_ids"],
    },
    "reviews_summary_get": {
        "fn": reviews_summary_get,
        "description": (
            "Rating average, count and 1-5 star distribution of one product, plus up to 5 recent "
            "positive and 5 recent negative review texts. Summarize praise and complaints only "
            "from these texts. empty=true means no reviews yet."
        ),
        "params": ["product_id"],
    },
    "search_products": {
        "fn": search_products,
        "description": (
            "Search products. query is free text (Arabic or English). category and brand are "
            "slugs. min_price and max_price are in EGP. in_stock_only defaults to true. "
            "sort: newest, price_asc, price_desc or rating. specs is an object: use "
            "<key>_min for 'at least' (ram_gb, storage_gb, battery_mah, battery_hours, "
            "camera_mp, screen_inch) and exact values for network (4g/5g), os, storage_type, "
            "type, connector, wireless, noise_cancelling. sort_spec sorts high to low by one "
            "of the *_min keys without the suffix, e.g. battery_mah. "
            "empty=true means nothing matched."
        ),
        "params": [
            "query",
            "category",
            "brand",
            "min_price",
            "max_price",
            "in_stock_only",
            "sort",
            "sort_spec",
            "specs",
            "limit",
        ],
    },
}


def call_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Single entry point for the graph/router. Unknown tools and extra args are rejected."""
    spec = REGISTRY.get(name)
    if spec is None:
        return {"ok": False, "error": "unknown_tool", "message": f"No tool named {name}"}
    extra = set(args) - set(spec["params"])
    if extra:
        # e.g. the model tried to pass customer_id
        return {
            "ok": False,
            "error": "forbidden_argument",
            "message": f"Not allowed: {sorted(extra)}",
        }
    try:
        return spec["fn"](ctx, **args)
    except TypeError:
        return {"ok": False, "error": "bad_arguments", "message": "Missing or wrong arguments"}
