from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import (
    ActorType,
    CancelReason,
    OrderStatus,
    ReturnReason,
    ReturnStatus,
)
from ai_commerce_marketplace.core.exceptions import ConflictError, NotFoundError
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import Order, OrderItem, Return
from ai_commerce_marketplace.services.order_rules import (
    Eligibility,
    check_cancel_eligibility,
    check_return_eligibility,
)
from ai_commerce_marketplace.services.order_state import change_status

ACTIVE_RETURN = (ReturnStatus.REQUESTED, ReturnStatus.APPROVED, ReturnStatus.RECEIVED)


def _owned_order(session: Session, customer_id: int, order_id: int, *, lock: bool) -> Order:
    stmt = select(Order).where(Order.id == order_id, Order.customer_id == customer_id)
    if lock:
        stmt = stmt.with_for_update()
    order = session.scalar(stmt)
    if order is None:
        raise NotFoundError("Order not found", code="order_not_found")
    return order


def _owned_order_locked(session: Session, customer_id: int, order_id: int) -> Order:
    return _owned_order(session, customer_id, order_id, lock=True)


def _order_item(session: Session, order: Order, item_id: int) -> OrderItem:
    item = session.scalar(
        select(OrderItem).where(OrderItem.id == item_id, OrderItem.order_id == order.id)
    )
    if item is None:
        raise NotFoundError("Order item not found", code="order_item_not_found")
    return item


def _return_verdict(
    session: Session, order: Order, item: OrderItem, qty: int, now: datetime
) -> Eligibility:
    """Pure return rules + the quantity check. Shared by the check and the action."""
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
    if verdict.allowed and not 1 <= qty <= item.qty:
        return Eligibility(False, "invalid_qty", f"Quantity must be between 1 and {item.qty}")
    return verdict


# ---- read-only checks (used by the Order Actions Agent before asking for confirmation) ----
def get_cancel_eligibility(
    session: Session, customer_id: int, order_id: int, *, now: datetime | None = None
) -> Eligibility:
    """Same rule cancel_order applies, without changing anything."""
    order = _owned_order(session, customer_id, order_id, lock=False)
    return check_cancel_eligibility(order.status, now or datetime.now(UTC))


def get_return_eligibility(
    session: Session,
    customer_id: int,
    order_id: int,
    item_id: int,
    qty: int | None = None,
    *,
    now: datetime | None = None,
) -> Eligibility:
    """Same rules request_return applies, without changing anything. qty=None means all."""
    order = _owned_order(session, customer_id, order_id, lock=False)
    item = _order_item(session, order, item_id)
    return _return_verdict(
        session, order, item, item.qty if qty is None else qty, now or datetime.now(UTC)
    )


# ---- actions ----
def cancel_order(
    session: Session,
    customer_id: int,
    order_id: int,
    *,
    actor_type: ActorType = ActorType.CUSTOMER,
    reason_code: str = CancelReason.CUSTOMER_REQUEST,
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
            reason_code=reason_code,
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
    qty: int | None = None,
    actor_type: ActorType = ActorType.CUSTOMER,
    now: datetime | None = None,
) -> Return:
    """qty=None returns the whole quantity of the item."""
    now = now or datetime.now(UTC)
    try:
        order = _owned_order_locked(session, customer_id, order_id)
        item = _order_item(session, order, item_id)
        qty = item.qty if qty is None else qty
        verdict = _return_verdict(session, order, item, qty, now)
        if not verdict.allowed:
            raise ConflictError(verdict.message, code=verdict.code)

        ret = Return(
            order_item_id=item.id,
            requested_by=customer_id,
            qty=qty,
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
                actor_type=actor_type,
                actor_user_id=customer_id,
                reason_code=reason_code,
                now=now,
            )
        session.commit()
        return ret
    except Exception:
        session.rollback()
        raise
