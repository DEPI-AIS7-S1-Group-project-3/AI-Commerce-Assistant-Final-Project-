from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import ReturnStatus
from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Return,
)
from ai_commerce_marketplace.database.models.seller import Seller
from ai_commerce_marketplace.schemas.order import (
    OrderDetailOut,
    OrderItemOut,
    OrderOut,
    TimelineEntry,
)
from ai_commerce_marketplace.services.order_rules import (
    check_cancel_eligibility,
    check_return_eligibility,
)

# Same set as services/order_actions.ACTIVE_RETURN (an item can have one active return).
ACTIVE_RETURN = (ReturnStatus.REQUESTED, ReturnStatus.APPROVED, ReturnStatus.RECEIVED)


def order_fields(
    session: Session, order: Order, items: list[OrderItem], now: datetime | None = None
) -> dict[str, Any]:
    """All OrderOut fields, incl. what the UI may do now (cancel / return per item).

    The flags use the same pure rules as order_actions, so the UI and the actions agree.
    The actions still re-check everything under a row lock.
    """
    now = now or datetime.now(UTC)
    seller_name = session.scalar(select(Seller.store_name).where(Seller.id == order.seller_id))

    returnable: dict[int, bool] = {}
    latest_return: dict[int, str] = {}
    if items:
        returnable = {
            pid: ok
            for pid, ok in session.execute(
                select(Product.id, Product.is_returnable).where(
                    Product.id.in_([i.product_id for i in items])
                )
            )
        }
        for item_id, status in session.execute(
            select(Return.order_item_id, Return.status)
            .where(Return.order_item_id.in_([i.id for i in items]))
            .order_by(Return.created_at, Return.id)
        ):
            latest_return[item_id] = status  # later rows overwrite: keeps the latest

    items_out = []
    for i in items:
        is_returnable = returnable.get(i.product_id, False)
        ret_status = latest_return.get(i.id)
        verdict = check_return_eligibility(
            order.status, order.delivered_at, is_returnable, ret_status in ACTIVE_RETURN, now
        )
        items_out.append(
            OrderItemOut(
                id=i.id,
                product_id=i.product_id,
                title=i.product_title_snapshot,
                qty=i.qty,
                unit_price_egp=i.unit_price_egp,
                line_total_egp=i.unit_price_egp * i.qty,
                is_returnable=is_returnable,
                return_status=ret_status,
                can_return=verdict.allowed,
                return_block=None if verdict.allowed else verdict.code,
            )
        )

    cancel = check_cancel_eligibility(order.status, now)
    return dict(
        id=order.id,
        checkout_group_id=str(order.checkout_group_id),
        seller_id=order.seller_id,
        seller_name=seller_name or "",
        status=order.status,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        shipping_address=order.shipping_address,
        subtotal_egp=order.subtotal_egp,
        shipping_fee_egp=order.shipping_fee_egp,
        total_egp=order.total_egp,
        expected_delivery_at=order.expected_delivery_at,
        delivered_at=order.delivered_at,
        created_at=order.created_at,
        can_cancel=cancel.allowed,
        cancel_block=None if cancel.allowed else cancel.code,
        items=items_out,
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
    return [
        OrderOut(**order_fields(session, o, _items_for(session, o.id)))
        for o in session.scalars(stmt).all()
    ]


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
    return OrderDetailOut(
        **order_fields(session, order, _items_for(session, order.id)), timeline=timeline
    )
