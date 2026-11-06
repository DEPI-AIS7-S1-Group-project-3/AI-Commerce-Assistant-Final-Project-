from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import OrderStatus, ReturnStatus
from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import Order, OrderItem, Return
from ai_commerce_marketplace.database.models.review import Review
from ai_commerce_marketplace.database.models.seller import Seller

EXCLUDED = (OrderStatus.CANCELLED, OrderStatus.RETURNED)
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class Period:
    date_from: datetime
    date_to: datetime


def seller_id_for_user(session: Session, user_id: int) -> int:
    """The only place a user becomes a seller id."""
    sid = session.scalar(select(Seller.id).where(Seller.user_id == user_id))
    if sid is None:
        raise NotFoundError("Seller profile not found", code="seller_not_found")
    return sid


def _in_period(stmt: Any, seller_id: int, p: Period) -> Any:
    """Restrict a statement to one seller and a [from, to) period on orders.created_at."""
    return stmt.where(
        Order.seller_id == seller_id,
        Order.created_at >= p.date_from,
        Order.created_at < p.date_to,
    )


def sales_summary(session: Session, seller_id: int, p: Period) -> dict[str, Any]:
    stmt = _in_period(
        select(
            func.coalesce(func.sum(OrderItem.line_total_egp), 0),
            func.coalesce(func.sum(OrderItem.qty), 0),
            func.count(func.distinct(Order.id)),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status.not_in(EXCLUDED)),
        seller_id,
        p,
    )
    revenue, units, orders = session.execute(stmt).one()
    revenue = Decimal(revenue).quantize(Decimal("0.01"))
    aov = (revenue / orders).quantize(Decimal("0.01"), ROUND_HALF_UP) if orders else ZERO
    return {
        "date_from": p.date_from.isoformat(),
        "date_to": p.date_to.isoformat(),
        "revenue": revenue,
        "units_sold": int(units),
        "orders_count": int(orders),
        "aov": aov,
    }


def _change(a: Decimal | int, b: Decimal | int) -> dict[str, Any]:
    delta = Decimal(b) - Decimal(a)
    pct = None
    if Decimal(a) != 0:
        pct = (delta / Decimal(a) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return {"a": a, "b": b, "delta": delta, "change_pct": pct}


def compare_periods(session: Session, seller_id: int, a: Period, b: Period) -> dict[str, Any]:
    sa, sb = sales_summary(session, seller_id, a), sales_summary(session, seller_id, b)
    return {
        "period_a": {"date_from": sa["date_from"], "date_to": sa["date_to"]},
        "period_b": {"date_from": sb["date_from"], "date_to": sb["date_to"]},
        **{k: _change(sa[k], sb[k]) for k in ("revenue", "units_sold", "orders_count", "aov")},
    }


def top_products(
    session: Session, seller_id: int, p: Period, limit: int = 5, worst: bool = False
) -> list[dict[str, Any]]:
    units = func.sum(OrderItem.qty).label("units")
    revenue = func.sum(OrderItem.line_total_egp).label("revenue")
    stmt = _in_period(
        select(Product.id, Product.title_ar, units, revenue)
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(Order.status.not_in(EXCLUDED)),
        seller_id,
        p,
    )
    order = units.asc() if worst else units.desc()
    stmt = stmt.group_by(Product.id, Product.title_ar).order_by(order, Product.id).limit(limit)
    return [
        {"product_id": r.id, "title": r.title_ar, "units_sold": int(r.units), "revenue": r.revenue}
        for r in session.execute(stmt)
    ]


def low_stock_products(
    session: Session, seller_id: int, threshold: int = 5
) -> list[dict[str, Any]]:
    stmt = (
        select(Product.id, Product.title_ar, Product.stock_qty)
        .where(
            Product.seller_id == seller_id,
            Product.is_active,
            Product.stock_qty <= threshold,
        )
        .order_by(Product.stock_qty, Product.id)
    )
    return [
        {"product_id": r.id, "title": r.title_ar, "stock_qty": r.stock_qty}
        for r in session.execute(stmt)
    ]


def orders_by_status(session: Session, seller_id: int, p: Period) -> dict[str, int]:
    stmt = _in_period(select(Order.status, func.count()).select_from(Order), seller_id, p).group_by(
        Order.status
    )
    return {status: int(n) for status, n in session.execute(stmt)}


def returns_report(session: Session, seller_id: int, p: Period) -> dict[str, Any]:
    stmt = _in_period(
        select(Return.reason_code, Return.status, func.count())
        .select_from(Return)
        .join(OrderItem, OrderItem.id == Return.order_item_id)
        .join(Order, Order.id == OrderItem.order_id),
        seller_id,
        p,
    ).group_by(Return.reason_code, Return.status)
    by_reason: dict[str, int] = {}
    total = 0
    for reason, status, n in session.execute(stmt):
        if status == ReturnStatus.REJECTED:
            continue
        by_reason[reason] = by_reason.get(reason, 0) + int(n)
        total += int(n)
    return {"total_returns": total, "by_reason": by_reason}


def product_reviews(session: Session, seller_id: int, product_id: int) -> dict[str, Any]:
    owned = session.scalar(
        select(Product.id).where(Product.id == product_id, Product.seller_id == seller_id)
    )
    if owned is None:  # same answer for "not yours" and "does not exist"
        raise NotFoundError("Product not found", code="product_not_found")
    avg, count = session.execute(
        select(func.avg(Review.rating), func.count()).where(Review.product_id == product_id)
    ).one()
    low = session.scalars(
        select(Review.body)
        .where(Review.product_id == product_id, Review.rating <= 2)
        .order_by(Review.created_at.desc())
        .limit(5)
    ).all()
    return {
        "product_id": product_id,
        "rating_avg": round(float(avg), 2) if avg is not None else None,
        "reviews_count": int(count),
        "recent_low_rated": list(low),
    }
