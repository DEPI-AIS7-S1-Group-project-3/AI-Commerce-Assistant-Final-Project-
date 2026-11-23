"""Tool layer for the Support Agent (read-only).

The agent answers customers' questions about their own orders and about the store policies.
It never changes anything: cancelling or returning is done by the Order Actions agent, after
an explicit confirmation from the customer.

Rules every tool follows:

- ``customer_id`` comes from ``ToolContext`` (the token). It is never a tool argument, so the
  model cannot ask for another customer's order. An order that is not the customer's is
  reported exactly like a missing one (``order_not_found``).
- Tools never raise to the agent. They return ``{"ok": True, ...}`` or
  ``{"ok": False, "error": code, "message": ...}``; an empty search is ``empty: True``.
- Every number and date comes from a service. Warranty end dates and return/cancel
  eligibility are computed in the backend, not by the model.
- Policy tools are open to visitors; order tools need a signed-in customer (``login_required``).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.common import (
    ToolInputError,
    clamp_limit,
    positive_id,
    safe,
)
from ai_commerce_marketplace.agents.common import (
    call_tool as _call_tool,
)
from ai_commerce_marketplace.services import order_support, orders, policies
from ai_commerce_marketplace.services import policy_search as policy_index

MAX_QUERY_CHARS = 300
POLICY_SLUGS = ("shipping", "returns", "warranty", "cancellation")


@dataclass(frozen=True)
class ToolContext:
    """Injected by the router from the token. Not visible to the LLM."""

    session: Session
    customer_id: int | None = None  # None = visitor (policy questions only)
    now: datetime | None = None  # only tests/eval set this; production uses the real clock


def _customer(ctx: ToolContext) -> int:
    if ctx.customer_id is None:
        raise ToolInputError("login_required", "The customer must be signed in to see orders")
    return ctx.customer_id


def _now(ctx: ToolContext) -> datetime:
    return ctx.now or datetime.now(UTC)


def _order_id(value: Any) -> int:
    return positive_id(value, code="invalid_order_id", name="order id")


IN_TRANSIT = ("pending", "confirmed", "shipped", "out_for_delivery")


def _days_late(o: Any, now: datetime) -> int:
    """Whole days past the expected delivery date, for orders that have not arrived."""
    if o.status in IN_TRANSIT and now > o.expected_delivery_at:
        return (now - o.expected_delivery_at).days
    return 0


def _compact_order(o: Any, now: datetime) -> dict[str, Any]:
    return {
        "order_id": o.id,
        "checkout_group_id": o.checkout_group_id,
        "seller_name": o.seller_name,
        "status": o.status,
        "payment_method": o.payment_method,
        "payment_status": o.payment_status,
        "total_egp": o.total_egp,
        "created_at": o.created_at,
        "expected_delivery_at": o.expected_delivery_at,
        "delivered_at": o.delivered_at,
        "days_late": _days_late(o, now),
        "can_cancel": o.can_cancel,
        "cancel_block": o.cancel_block,
        "items": [{"item_id": i.id, "title": i.title, "qty": i.qty} for i in o.items],
    }


# ---------------------------------------------------------------- policies
def policy_search(ctx: ToolContext, query: str, limit: int = 3) -> dict[str, Any]:
    """Best matching policy sections for a question, each with its source.

    Args:
        query: The customer's question in their own words, e.g. "الشحن بكام؟".
        limit: How many sections to return, 1 to 5 (default 3).
    """

    def run() -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ToolInputError("empty_query", "query must be non-empty text")
        hits = policy_index.search_policies(
            ctx.session, query.strip()[:MAX_QUERY_CHARS], clamp_limit(limit, 5)
        )
        return {
            "empty": not hits,
            "sections": [
                {
                    "policy_slug": h.doc.slug,
                    "policy_title": h.doc.policy_title,
                    "version": h.doc.version,
                    "section_no": h.doc.no,
                    "section_title": h.doc.title,
                    "text": h.doc.body,
                    "score": h.score,
                }
                for h in hits
            ],
        }

    return safe(run)


def policy_get(
    ctx: ToolContext,
    slug: Literal["shipping", "returns", "warranty", "cancellation"],
    section_no: int | None = None,
) -> dict[str, Any]:
    """One whole policy, or one numbered section of it.

    Args:
        slug: Which policy to read.
        section_no: Section number inside the policy, e.g. 3. Leave empty for the whole policy.
    """

    def run() -> dict[str, Any]:
        if slug not in POLICY_SLUGS:
            raise ToolInputError("invalid_slug", f"slug must be one of {list(POLICY_SLUGS)}")
        policy = policies.get_policy(ctx.session, slug)
        sections = policy.sections
        if section_no is not None:
            no = positive_id(section_no, code="invalid_section", name="section number")
            sections = [s for s in sections if s.no == no]
            if not sections:
                raise ToolInputError("section_not_found", f"{slug} has no section {no}")
        return {
            "policy_slug": policy.slug,
            "policy_title": policy.title_ar,
            "version": policy.version,
            "sections": [
                {"section_no": s.no, "section_title": s.title, "text": s.body} for s in sections
            ],
        }

    return safe(run)


# ------------------------------------------------------------------ orders
def order_list(ctx: ToolContext, limit: int = 5) -> dict[str, Any]:
    """The customer's most recent orders (newest first), in short form.

    Args:
        limit: How many orders to return, 1 to 10 (default 5).
    """

    def run() -> dict[str, Any]:
        customer_id = _customer(ctx)
        n = clamp_limit(limit, 10)
        rows = orders.list_orders(ctx.session, customer_id, _now(ctx))
        return {
            "empty": not rows,
            "total_orders": len(rows),
            "orders": [_compact_order(o, _now(ctx)) for o in rows[:n]],
        }

    return safe(run)


def order_get(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    """One order of the customer: items, status, expected delivery and the status timeline.

    Args:
        order_id: The order number the customer mentioned, e.g. 10002.
    """

    def run() -> dict[str, Any]:
        order = orders.get_order(ctx.session, _customer(ctx), _order_id(order_id), _now(ctx))
        return {
            **_compact_order(order, _now(ctx)),
            "subtotal_egp": order.subtotal_egp,
            "shipping_fee_egp": order.shipping_fee_egp,
            "shipping_governorate": order.shipping_address.get("governorate"),
            "shipping_city": order.shipping_address.get("city"),
            "timeline": [
                {"from": t.from_status, "to": t.to_status, "by": t.actor_type, "at": t.created_at}
                for t in order.timeline
            ],
        }

    return safe(run)


def order_eligibility(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    """Can the whole order be cancelled, and can each item be returned? With the reason if not.

    Answers come from the same rules the API enforces (``order_rules``).

    Args:
        order_id: The order number the customer mentioned, e.g. 10002.
    """

    def run() -> dict[str, Any]:
        order = orders.get_order(ctx.session, _customer(ctx), _order_id(order_id), _now(ctx))
        return {
            "order_id": order.id,
            "status": order.status,
            "can_cancel": order.can_cancel,
            "cancel_block": order.cancel_block,
            "items": [
                {
                    "item_id": i.id,
                    "title": i.title,
                    "is_returnable": i.is_returnable,
                    "can_return": i.can_return,
                    "return_block": i.return_block,
                    "return_status": i.return_status,
                }
                for i in order.items
            ],
        }

    return safe(run)


def warranty_status(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    """Warranty start, end and days left for each item of an order (counted from delivery).

    Args:
        order_id: The order number the customer mentioned, e.g. 10003.
    """

    def run() -> dict[str, Any]:
        return order_support.order_warranty(
            ctx.session, _customer(ctx), _order_id(order_id), _now(ctx)
        )

    return safe(run)


def return_status(ctx: ToolContext, order_id: int) -> dict[str, Any]:
    """Return requests already made on an order, with their status.

    Args:
        order_id: The order number the customer mentioned, e.g. 10003.
    """

    def run() -> dict[str, Any]:
        out = order_support.order_returns(ctx.session, _customer(ctx), _order_id(order_id))
        return {**out, "empty": not out["returns"]}

    return safe(run)


REGISTRY: dict[str, dict[str, Any]] = {
    "policy_search": {
        "fn": policy_search,
        "description": "Find the policy sections that answer a question. "
        "Use for any policy question.",
        "params": ["query", "limit"],
    },
    "policy_get": {
        "fn": policy_get,
        "description": "Read a whole policy or one numbered section "
        "(slug: shipping, returns, warranty, cancellation).",
        "params": ["slug", "section_no"],
    },
    "order_list": {
        "fn": order_list,
        "description": "The customer's latest orders. Use when they do not say which order.",
        "params": ["limit"],
    },
    "order_get": {
        "fn": order_get,
        "description": "Status, items, expected delivery and timeline of one order.",
        "params": ["order_id"],
    },
    "order_eligibility": {
        "fn": order_eligibility,
        "description": "Whether an order can be cancelled and each item returned, and why not.",
        "params": ["order_id"],
    },
    "warranty_status": {
        "fn": warranty_status,
        "description": "Warranty end date and days left for each item of an order.",
        "params": ["order_id"],
    },
    "return_status": {
        "fn": return_status,
        "description": "Status of return requests already made on an order.",
        "params": ["order_id"],
    },
}


def call_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Single entry point for the graph/router."""
    return _call_tool(REGISTRY, ctx, name, args)


__all__ = ["REGISTRY", "ToolContext", "call_tool"]
