from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import ActorType, OrderStatus, ReturnReason, ReturnStatus
from ai_commerce_marketplace.core.exceptions import ConflictError, NotFoundError
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import Order, OrderItem, Return
from ai_commerce_marketplace.services.order_rules import (
    check_cancel_eligibility,
    check_return_eligibility,
)
from ai_commerce_marketplace.services.order_state import change_status

ACTIVE_RETURN = (ReturnStatus.REQUESTED, ReturnStatus.APPROVED, ReturnStatus.RECEIVED)


def _owned_order_locked(session: Session, customer_id: int, order_id: int) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.customer_id == customer_id)
        .with_for_update()
    )
    order = session.scalar(stmt)
    if order is None:
        raise NotFoundError("Order not found", code="order_not_found")
    return order


def cancel_order(
    session: Session,
    customer_id: int,
    order_id: int,
    *,
    actor_type: ActorType = ActorType.CUSTOMER,
    now: datetime | None = None,
) -> Order:
    now = now or datetime.now(UTC)
    try:
        order = _owned_order_locked(session, customer_id, order_id)
        verdict = check_cancel_eligibility(order.status, now)
        if not verdict.allowed:
            raise ConflictError(verdict.message, code=verdict.code)

        items = list(session.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
        product_ids = sorted(i.product_id for i in items)
        products = {
            p.id: p
            for p in session.scalars(
                select(Product)
                .where(Product.id.in_(product_ids))
                .order_by(Product.id)
                .with_for_update()
            )
        }
        for item in items:
            products[item.product_id].stock_qty += item.qty  # restore stock

        change_status(
            session,
            order,
            OrderStatus.CANCELLED,
            actor_type=actor_type,
            actor_user_id=customer_id,
            reason_code="customer_request",
            now=now,
        )
        session.commit()
        return order
    except Exception:
        session.rollback()
        raise


def request_return(
    session: Session,
    customer_id: int,
    order_id: int,
    item_id: int,
    reason_code: ReturnReason,
    reason_text: str | None,
    *,
    now: datetime | None = None,
) -> Return:
    now = now or datetime.now(UTC)
    try:
        order = _owned_order_locked(session, customer_id, order_id)
        item = session.scalar(
            select(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == order.id)
        )
        if item is None:
            raise NotFoundError("Order item not found", code="order_item_not_found")
        product = session.get(Product, item.product_id)
        has_active = (
            session.scalar(
                select(Return.id).where(
                    Return.order_item_id == item.id, Return.status.in_(ACTIVE_RETURN)
                )
            )
            is not None
        )
        verdict = check_return_eligibility(
            order.status,
            order.delivered_at,
            bool(product and product.is_returnable),
            has_active,
            now,
        )
        if not verdict.allowed:
            raise ConflictError(verdict.message, code=verdict.code)

        ret = Return(
            order_item_id=item.id,
            requested_by=customer_id,
            qty=item.qty,
            reason_code=reason_code,
            reason_text=reason_text,
            status=ReturnStatus.REQUESTED,
        )
        session.add(ret)
        if order.status == OrderStatus.DELIVERED:
            change_status(
                session,
                order,
                OrderStatus.RETURN_REQUESTED,
                actor_type=ActorType.CUSTOMER,
                actor_user_id=customer_id,
                reason_code=reason_code,
                now=now,
            )
        session.commit()
        return ret
    except Exception:
        session.rollback()
        raise
