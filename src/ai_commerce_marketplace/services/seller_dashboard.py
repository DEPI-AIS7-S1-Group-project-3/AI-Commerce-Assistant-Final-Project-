"""Seller dashboard + seller order handling for the web UI.

Numbers reuse services/seller_analytics.py (same definitions as the Seller agent, see
docs/seller-metrics.md). This file only adds what the UI needs on top: a daily series,
the seller's order list, and moving an order forward one step.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import ActorType, OrderStatus, PaymentMethod, PaymentStatus
from ai_commerce_marketplace.core.exceptions import ConflictError, NotFoundError
from ai_commerce_marketplace.database.models.order import Order, OrderItem
from ai_commerce_marketplace.database.models.seller import Seller
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.schemas.seller import (
    DailyPoint,
    KpiChange,
    Kpis,
    LowStockProduct,
    SellerDashboardOut,
    SellerOrderItemOut,
    SellerOrderOut,
    TopProduct,
)
from ai_commerce_marketplace.services import seller_analytics as sa
from ai_commerce_marketplace.services.order_state import change_status

S = OrderStatus
TZ = "Africa/Cairo"  # days in the chart are Cairo calendar days
LOW_STOCK = 5

# The only moves a seller can make: one step forward. (Cancel is the customer's action.)
NEXT: dict[str, str] = {
    S.PENDING: S.CONFIRMED,
    S.CONFIRMED: S.SHIPPED,
    S.SHIPPED: S.OUT_FOR_DELIVERY,
    S.OUT_FOR_DELIVERY: S.DELIVERED,
}


def dashboard(
    session: Session, seller_id: int, days: int = 30, now: datetime | None = None
) -> SellerDashboardOut:
    now = now or datetime.now(UTC)
    cur = sa.Period(now - timedelta(days=days), now)
    prev = sa.Period(now - timedelta(days=2 * days), cur.date_from)

    summary = sa.sales_summary(session, seller_id, cur)
    cmp = sa.compare_periods(session, seller_id, prev, cur)
    store = session.scalar(select(Seller.store_name).where(Seller.id == seller_id)) or ""
    by_status = sa.orders_by_status(session, seller_id, cur)
    pending_actions = session.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.seller_id == seller_id, Order.status.in_(list(NEXT)))
    )

    return SellerDashboardOut(
        store_name=store,
        days=days,
        kpis=Kpis(**{k: summary[k] for k in ("revenue", "units_sold", "orders_count", "aov")}),
        change=KpiChange(
            revenue_pct=cmp["revenue"]["change_pct"],
            units_sold_pct=cmp["units_sold"]["change_pct"],
            orders_count_pct=cmp["orders_count"]["change_pct"],
            aov_pct=cmp["aov"]["change_pct"],
        ),
        daily=_daily(session, seller_id, cur),
        top_products=[TopProduct(**r) for r in sa.top_products(session, seller_id, cur, limit=5)],
        low_stock=[
            LowStockProduct(**r) for r in sa.low_stock_products(session, seller_id, LOW_STOCK)
        ],
        orders_by_status=by_status,
        pending_actions=pending_actions or 0,
    )


def _daily(session: Session, seller_id: int, p: sa.Period) -> list[DailyPoint]:
    """Revenue and order count per Cairo day, every day of the period (zeros included)."""
    day = func.date(func.timezone(TZ, Order.created_at))
    stmt = (
        select(
            day,
            func.coalesce(func.sum(OrderItem.line_total_egp), 0),
            func.count(func.distinct(Order.id)),
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.seller_id == seller_id,
            Order.created_at >= p.date_from,
            Order.created_at < p.date_to,
            Order.status.not_in(sa.EXCLUDED),  # same "counted orders" rule as the KPIs
        )
        .group_by(day)
    )
    found: dict[date, tuple[Decimal, int]] = {
        d: (Decimal(r), int(n)) for d, r, n in session.execute(stmt)
    }
    first = _cairo_day(session, p.date_from)
    last = _cairo_day(session, p.date_to - timedelta(microseconds=1))
    out = []
    d = first
    while d <= last:
        r, n = found.get(d, (Decimal("0.00"), 0))
        out.append(DailyPoint(day=d, revenue=Decimal(r).quantize(Decimal("0.01")), orders=n))
        d += timedelta(days=1)
    return out


def _cairo_day(session: Session, ts: datetime) -> date:
    return session.scalar(select(func.date(func.timezone(TZ, ts))))  # type: ignore[return-value]


def _order_out(session: Session, o: Order) -> SellerOrderOut:
    items = session.scalars(
        select(OrderItem).where(OrderItem.order_id == o.id).order_by(OrderItem.id)
    )
    full_name = session.scalar(select(User.full_name).where(User.id == o.customer_id)) or ""
    addr = o.shipping_address or {}
    return SellerOrderOut(
        id=o.id,
        created_at=o.created_at,
        status=o.status,
        next_status=NEXT.get(o.status),
        payment_method=o.payment_method,
        payment_status=o.payment_status,
        customer_name=full_name.split()[0] if full_name.strip() else "",
        governorate=addr.get("governorate"),
        city=addr.get("city"),
        subtotal_egp=o.subtotal_egp,
        shipping_fee_egp=o.shipping_fee_egp,
        total_egp=o.total_egp,
        expected_delivery_at=o.expected_delivery_at,
        delivered_at=o.delivered_at,
        items=[
            SellerOrderItemOut(
                product_id=i.product_id,
                title=i.product_title_snapshot,
                qty=i.qty,
                line_total_egp=i.unit_price_egp * i.qty,
            )
            for i in items
        ],
    )


def list_orders(
    session: Session, seller_id: int, status: str | None = None, limit: int = 50, offset: int = 0
) -> list[SellerOrderOut]:
    stmt = select(Order).where(Order.seller_id == seller_id)
    if status:
        stmt = stmt.where(Order.status == status)
    stmt = stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).offset(offset)
    return [_order_out(session, o) for o in session.scalars(stmt).all()]


def advance_order(
    session: Session, seller_id: int, user_id: int, order_id: int, to_status: str
) -> SellerOrderOut:
    """Move one of the seller's orders exactly one step forward. Locks the order row."""
    try:
        order = session.scalar(
            select(Order)
            .where(Order.id == order_id, Order.seller_id == seller_id)
            .with_for_update()
        )
        if order is None:  # also when it belongs to another seller: don't reveal it exists
            raise NotFoundError("Order not found", code="order_not_found")
        if NEXT.get(order.status) != to_status:
            raise ConflictError(
                f"Cannot move this order from {order.status} to {to_status}",
                code="invalid_transition",
                details={"from": order.status, "to": to_status, "next": NEXT.get(order.status)},
            )
        change_status(session, order, to_status, actor_type=ActorType.SELLER, actor_user_id=user_id)
        # Cash on delivery is collected on delivery (documented in docs/demo-data.md).
        if to_status == S.DELIVERED and order.payment_method == PaymentMethod.COD:
            order.payment_status = PaymentStatus.PAID
        session.commit()
        return _order_out(session, order)
    except Exception:
        session.rollback()
        raise
