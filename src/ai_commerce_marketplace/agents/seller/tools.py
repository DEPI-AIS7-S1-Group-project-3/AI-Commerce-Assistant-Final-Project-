from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import AppError
from ai_commerce_marketplace.services import seller_analytics as sa
from ai_commerce_marketplace.services.seller_analytics import Period

MAX_PERIOD_DAYS = 366
MAX_LIMIT = 20


@dataclass(frozen=True)
class ToolContext:
    """Injected by the router from the token. Not visible to the LLM."""

    session: Session
    seller_id: int


class ToolInputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _parse_date(value: str, name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolInputError(
            "invalid_date", f"{name} must be an ISO date like 2026-10-01"
        ) from None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _period(date_from: str, date_to: str, name: str = "period") -> Period:
    start = _parse_date(date_from, f"{name}.date_from")
    end = _parse_date(date_to, f"{name}.date_to")
    if end <= start:
        raise ToolInputError("invalid_period", f"{name}: date_to must be after date_from")
    if end - start > timedelta(days=MAX_PERIOD_DAYS):
        raise ToolInputError("period_too_long", f"{name}: at most {MAX_PERIOD_DAYS} days")
    return Period(start, end)


def _limit(value: int) -> int:
    if not isinstance(value, int) or value < 1:
        raise ToolInputError("invalid_limit", "limit must be a positive integer")
    return min(value, MAX_LIMIT)


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
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


# ---- tools ----
def get_sales_summary(ctx: ToolContext, date_from: str, date_to: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        s = sa.sales_summary(ctx.session, ctx.seller_id, _period(date_from, date_to))
        return {**s, "empty": s["orders_count"] == 0}

    return _safe(run)


def compare_periods(
    ctx: ToolContext, a_from: str, a_to: str, b_from: str, b_to: str
) -> dict[str, Any]:
    """period_a is the baseline (earlier), period_b the later one."""

    def run() -> dict[str, Any]:
        pa, pb = _period(a_from, a_to, "period_a"), _period(b_from, b_to, "period_b")
        c = sa.compare_periods(ctx.session, ctx.seller_id, pa, pb)
        empty = c["orders_count"]["a"] == 0 and c["orders_count"]["b"] == 0
        return {**c, "empty": empty}

    return _safe(run)


def top_products(
    ctx: ToolContext, date_from: str, date_to: str, limit: int = 5, worst: bool = False
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        rows = sa.top_products(
            ctx.session, ctx.seller_id, _period(date_from, date_to), _limit(limit), bool(worst)
        )
        return {"products": rows, "empty": not rows}

    return _safe(run)


def low_stock_products(ctx: ToolContext, threshold: int = 5) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        if not isinstance(threshold, int) or threshold < 0:
            raise ToolInputError("invalid_threshold", "threshold must be 0 or more")
        rows = sa.low_stock_products(ctx.session, ctx.seller_id, threshold)
        return {"threshold": threshold, "products": rows, "empty": not rows}

    return _safe(run)


def orders_by_status(ctx: ToolContext, date_from: str, date_to: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        counts = sa.orders_by_status(ctx.session, ctx.seller_id, _period(date_from, date_to))
        return {"by_status": counts, "empty": not counts}

    return _safe(run)


def returns_report(ctx: ToolContext, date_from: str, date_to: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        r = sa.returns_report(ctx.session, ctx.seller_id, _period(date_from, date_to))
        return {**r, "empty": r["total_returns"] == 0}

    return _safe(run)


def get_product_reviews(ctx: ToolContext, product_id: int) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        r = sa.product_reviews(ctx.session, ctx.seller_id, product_id)
        return {**r, "empty": r["reviews_count"] == 0}

    return _safe(run)


# What the LLM may fill in. ctx is never listed here.
REGISTRY: dict[str, dict[str, Any]] = {
    "get_sales_summary": {
        "fn": get_sales_summary,
        "description": "Revenue, units, orders count and average order value for a period.",
        "params": ["date_from", "date_to"],
    },
    "compare_periods": {
        "fn": compare_periods,
        "description": "Difference and percent change between two periods (a = baseline).",
        "params": ["a_from", "a_to", "b_from", "b_to"],
    },
    "top_products": {
        "fn": top_products,
        "description": "Best (or worst) selling products in a period.",
        "params": ["date_from", "date_to", "limit", "worst"],
    },
    "low_stock_products": {
        "fn": low_stock_products,
        "description": "Active products with stock at or below a threshold (0 = out of stock).",
        "params": ["threshold"],
    },
    "orders_by_status": {
        "fn": orders_by_status,
        "description": "Number of orders per status in a period.",
        "params": ["date_from", "date_to"],
    },
    "returns_report": {
        "fn": returns_report,
        "description": "Returns count and reasons in a period (rejected returns excluded).",
        "params": ["date_from", "date_to"],
    },
    "get_product_reviews": {
        "fn": get_product_reviews,
        "description": "Rating average, count and recent low-rated reviews of a product.",
        "params": ["product_id"],
    },
}


def call_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Single entry point for the graph/router. Unknown tools and extra args are rejected."""
    spec = REGISTRY.get(name)
    if spec is None:
        return {"ok": False, "error": "unknown_tool", "message": f"No tool named {name}"}
    extra = set(args) - set(spec["params"])
    if extra:
        # e.g. the model tried to pass seller_id
        return {
            "ok": False,
            "error": "forbidden_argument",
            "message": f"Not allowed: {sorted(extra)}",
        }
    try:
        return spec["fn"](ctx, **args)
    except TypeError:
        return {"ok": False, "error": "bad_arguments", "message": "Missing or wrong arguments"}
