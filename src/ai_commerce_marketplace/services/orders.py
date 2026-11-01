from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.order import (
    Order,
    OrderItem,
    OrderStatusHistory,
)
from ai_commerce_marketplace.schemas.order import (
    OrderDetailOut,
    OrderItemOut,
    OrderOut,
    TimelineEntry,
)


def _items_out(items: list[OrderItem]) -> list[OrderItemOut]:
    return [
        OrderItemOut(
            product_id=i.product_id,
            title=i.product_title_snapshot,
            qty=i.qty,
            unit_price_egp=i.unit_price_egp,
            line_total_egp=i.unit_price_egp * i.qty,
        )
        for i in items
    ]


def _order_fields(order: Order, items: list[OrderItem]) -> dict:
    return dict(
        id=order.id,
        seller_id=order.seller_id,
        status=order.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        shipping_address=order.shipping_address,
        subtotal_egp=order.subtotal_egp,
        shipping_fee_egp=order.shipping_fee_egp,
        total_egp=order.total_egp,
        expected_delivery_at=order.expected_delivery_at,
        created_at=order.created_at,
        items=_items_out(items),
    )


def _items_for(session: Session, order_id: int) -> list[OrderItem]:
    stmt = select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
    return list(session.scalars(stmt))


def list_orders(session: Session, customer_id: int) -> list[OrderOut]:
    stmt = (
        select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return [OrderOut(**_order_fields(o, _items_for(session, o.id))) for o in session.scalars(stmt)]


def get_order(session: Session, customer_id: int, order_id: int) -> OrderDetailOut:
    stmt = select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
    order = session.scalar(stmt)
    if order is None:
        raise NotFoundError("Order not found", code="order_not_found")
    history = session.scalars(
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.created_at, OrderStatusHistory.id)
    )
    timeline = [
        TimelineEntry(
            from_status=h.from_status,
            to_status=h.to_status,
            actor_type=h.actor_type,
            created_at=h.created_at,
        )
        for h in history
    ]
    return OrderDetailOut(**_order_fields(order, _items_for(session, order.id)), timeline=timeline)
