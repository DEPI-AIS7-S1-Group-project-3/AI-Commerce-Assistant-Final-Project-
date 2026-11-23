"""Read-only tools for the Seller Agent.

Rules (see the Agents guide):
- seller_id comes from ToolContext (the token), never from the LLM.
- Tools only call services.seller_analytics. No SQL, no models.
- Numbers come from tools, never from the model.
- Errors and empty results are returned as data so the agent can say so and not guess.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents import common
from ai_commerce_marketplace.agents.common import ToolInputError, clamp_limit, safe
from ai_commerce_marketplace.agents.seller import schemas as sc
from ai_commerce_marketplace.services import seller_analytics as sa
from ai_commerce_marketplace.services.seller_analytics import Period

MAX_PERIOD_DAYS = 366


@dataclass(frozen=True)
class ToolContext:
    """Injected by the router from the token. Not visible to the LLM."""

    session: Session
    seller_id: int


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


# ---- tools ----
def get_sales_summary(ctx: ToolContext, date_from: str, date_to: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        raw = sa.sales_summary(ctx.session, ctx.seller_id, _period(date_from, date_to))
        s = sc.SalesSummary(**raw)
        return {**s.model_dump(mode="json"), "empty": s.orders_count == 0}

    return safe(run)


def compare_periods(
    ctx: ToolContext, a_from: str, a_to: str, b_from: str, b_to: str
) -> dict[str, Any]:
    """period_a is the baseline (earlier), period_b the later one."""

    def run() -> dict[str, Any]:
        pa, pb = _period(a_from, a_to, "period_a"), _period(b_from, b_to, "period_b")
        c = sc.PeriodComparison(**sa.compare_periods(ctx.session, ctx.seller_id, pa, pb))
        empty = c.orders_count.a == 0 and c.orders_count.b == 0
        return {**c.model_dump(mode="json"), "empty": empty}

    return safe(run)


def top_products(
    ctx: ToolContext, date_from: str, date_to: str, limit: int = 5, worst: bool = False
) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        raw = sa.top_products(
            ctx.session,
            ctx.seller_id,
            _period(date_from, date_to),
            clamp_limit(limit),
            bool(worst),
        )
        rows = [sc.TopProduct(**r) for r in raw]
        return {"products": rows, "empty": not rows}

    return safe(run)


def low_stock_products(ctx: ToolContext, threshold: int = 5) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
            raise ToolInputError("invalid_threshold", "threshold must be 0 or more")
        raw = sa.low_stock_products(ctx.session, ctx.seller_id, threshold)
        rows = [sc.LowStockProduct(**r) for r in raw]
        return {"threshold": threshold, "products": rows, "empty": not rows}

    return safe(run)


def orders_by_status(ctx: ToolContext, date_from: str, date_to: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        counts = sa.orders_by_status(ctx.session, ctx.seller_id, _period(date_from, date_to))
        return {"by_status": counts, "empty": not counts}

    return safe(run)


def returns_report(ctx: ToolContext, date_from: str, date_to: str) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        raw = sa.returns_report(ctx.session, ctx.seller_id, _period(date_from, date_to))
        r = sc.ReturnsReport(**raw)
        return {**r.model_dump(mode="json"), "empty": r.total_returns == 0}

    return safe(run)


def get_product_reviews(ctx: ToolContext, product_id: int) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        r = sc.ProductReviews(**sa.product_reviews(ctx.session, ctx.seller_id, product_id))
        return {**r.model_dump(mode="json"), "empty": r.reviews_count == 0}

    return safe(run)


_DATE = {"type": "string", "description": "ISO date, e.g. 2026-10-06 (end is exclusive)"}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


# What the LLM may fill in. ctx is never listed here.
REGISTRY: dict[str, dict[str, Any]] = {
    "get_sales_summary": {
        "fn": get_sales_summary,
        "description": "Revenue, units, orders count and average order value for a period.",
        "params": ["date_from", "date_to"],
        "schema": _schema({"date_from": _DATE, "date_to": _DATE}, ["date_from", "date_to"]),
    },
    "compare_periods": {
        "fn": compare_periods,
        "description": "Difference and percent change between two periods (a = baseline).",
        "params": ["a_from", "a_to", "b_from", "b_to"],
        "schema": _schema(
            {"a_from": _DATE, "a_to": _DATE, "b_from": _DATE, "b_to": _DATE},
            ["a_from", "a_to", "b_from", "b_to"],
        ),
    },
    "top_products": {
        "fn": top_products,
        "description": "Best (or worst) selling products in a period.",
        "params": ["date_from", "date_to", "limit", "worst"],
        "schema": _schema(
            {
                "date_from": _DATE,
                "date_to": _DATE,
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "worst": {"type": "boolean"},
            },
            ["date_from", "date_to"],
        ),
    },
    "low_stock_products": {
        "fn": low_stock_products,
        "description": "Active products with stock at or below a threshold (0 = out of stock).",
        "params": ["threshold"],
        "schema": _schema({"threshold": {"type": "integer", "minimum": 0}}, []),
    },
    "orders_by_status": {
        "fn": orders_by_status,
        "description": "Number of orders per status in a period.",
        "params": ["date_from", "date_to"],
        "schema": _schema({"date_from": _DATE, "date_to": _DATE}, ["date_from", "date_to"]),
    },
    "returns_report": {
        "fn": returns_report,
        "description": "Returns count and reasons in a period (rejected returns excluded).",
        "params": ["date_from", "date_to"],
        "schema": _schema({"date_from": _DATE, "date_to": _DATE}, ["date_from", "date_to"]),
    },
    "get_product_reviews": {
        "fn": get_product_reviews,
        "description": "Rating average, count and recent low-rated reviews of a product.",
        "params": ["product_id"],
        "schema": _schema({"product_id": {"type": "integer", "minimum": 1}}, ["product_id"]),
    },
}


def call_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Single entry point. Delegates to the shared implementation in agents/common.py."""
    return common.call_tool(REGISTRY, ctx, name, args)
