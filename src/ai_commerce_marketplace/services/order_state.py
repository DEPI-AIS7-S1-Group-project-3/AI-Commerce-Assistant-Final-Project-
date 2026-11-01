from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import ActorType, OrderStatus
from ai_commerce_marketplace.core.exceptions import ConflictError
from ai_commerce_marketplace.database.models.order import Order, OrderStatusHistory

S = OrderStatus

# Allowed transitions. Terminal states (cancelled, returned) have no outgoing edges.
TRANSITIONS: dict[str, frozenset[str]] = {
    S.PENDING: frozenset({S.CONFIRMED, S.CANCELLED}),
    S.CONFIRMED: frozenset({S.SHIPPED, S.CANCELLED}),
    S.SHIPPED: frozenset({S.OUT_FOR_DELIVERY}),
    S.OUT_FOR_DELIVERY: frozenset({S.DELIVERED}),
    S.DELIVERED: frozenset({S.RETURN_REQUESTED}),
    S.RETURN_REQUESTED: frozenset({S.RETURNED}),
    S.CANCELLED: frozenset(),
    S.RETURNED: frozenset(),
}


def can_transition(current: str, target: str) -> bool:
    """Pure check: is current -> target an allowed edge?"""
    return target in TRANSITIONS.get(current, frozenset())


def change_status(
    session: Session,
    order: Order,
    target: str,
    *,
    actor_type: ActorType,
    actor_user_id: int | None = None,
    reason_code: str | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Order:
    """The only place an order's status may change.

    Validates the transition, keeps the DB date constraints consistent,
    and writes one order_status_history row. Does not commit.
    """
    current = order.status
    if not can_transition(current, target):
        raise ConflictError(
            f"Cannot change order status from {current} to {target}",
            code="invalid_transition",
            details={"from": current, "to": target},
        )
    now = now or datetime.now(UTC)

    order.status = target
    if target == S.DELIVERED:
        order.delivered_at = now
    if target == S.CANCELLED:
        order.cancelled_at = now
        order.cancel_reason_code = reason_code

    session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=current,
            to_status=target,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            reason_code=reason_code,
            note=note,
        )
    )
    session.flush()
    return order
