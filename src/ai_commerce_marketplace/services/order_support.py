"""Read-only order facts for customer support (warranty and returns of the customer's own orders).

Every function takes ``customer_id`` (resolved from the token) and answers "not found" for an
order that is not the customer's, exactly like a missing order. Dates are computed here so the
Support Agent never does date arithmetic itself.
"""

import calendar
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import Order, OrderItem, Return


def add_months(start: datetime, months: int) -> datetime:
    """``start`` plus whole calendar months; the day is clamped (Jan 31 + 1 month = Feb 28)."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def owned_order(session: Session, customer_id: int, order_id: int) -> Order:
    order = session.scalar(
        select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
    )
    if order is None:
        raise NotFoundError("Order not found", code="order_not_found")
    return order


def order_warranty(
    session: Session, customer_id: int, order_id: int, now: datetime | None = None
) -> dict[str, Any]:
    """Warranty window of each item. It starts at ``delivered_at`` (see the warranty policy)."""
    now = now or datetime.now(UTC)
    order = owned_order(session, customer_id, order_id)
    rows = session.execute(
        select(OrderItem, Product.warranty_months)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order.id)
        .order_by(OrderItem.id)
    ).all()

    items = []
    for item, months in rows:
        entry: dict[str, Any] = {
            "item_id": item.id,
            "product_id": item.product_id,
            "title": item.product_title_snapshot,
            "warranty_months": months,
            "starts_at": None,
            "ends_at": None,
            "days_left": None,
        }
        if months == 0:
            entry["state"] = "no_warranty"
        elif order.delivered_at is None:
            entry["state"] = "not_started"  # the clock starts at delivery
        else:
            ends = add_months(order.delivered_at, months)
            entry["starts_at"] = order.delivered_at
            entry["ends_at"] = ends
            entry["state"] = "active" if now <= ends else "expired"
            entry["days_left"] = max((ends - now).days, 0)
        items.append(entry)
    return {"order_id": order.id, "order_status": order.status, "items": items}


def order_returns(session: Session, customer_id: int, order_id: int) -> dict[str, Any]:
    """Every return request on the order, oldest first, with its current status."""
    order = owned_order(session, customer_id, order_id)
    rows = session.execute(
        select(Return, OrderItem.product_title_snapshot)
        .join(OrderItem, OrderItem.id == Return.order_item_id)
        .where(OrderItem.order_id == order.id)
        .order_by(Return.created_at, Return.id)
    ).all()
    returns = [
        {
            "return_id": r.id,
            "item_id": r.order_item_id,
            "title": title,
            "qty": r.qty,
            "status": r.status,
            "reason_code": r.reason_code,
            "reason_text": r.reason_text,
            "requested_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r, title in rows
    ]
    return {"order_id": order.id, "order_status": order.status, "returns": returns}
