from dataclasses import dataclass
from datetime import datetime, timedelta

from ai_commerce_marketplace.core.enums import OrderStatus

RETURN_WINDOW_DAYS = 14
CANCELLABLE = frozenset({OrderStatus.PENDING, OrderStatus.CONFIRMED})


@dataclass(frozen=True)
class Eligibility:
    allowed: bool
    code: str
    message: str


def check_cancel_eligibility(order_status: str, now: datetime) -> Eligibility:
    """Pure rule: an order can be cancelled only before it ships."""
    if order_status in CANCELLABLE:
        return Eligibility(True, "ok", "The order can be cancelled")
    if order_status == OrderStatus.CANCELLED:
        return Eligibility(False, "already_cancelled", "The order is already cancelled")
    if order_status in {OrderStatus.RETURN_REQUESTED, OrderStatus.RETURNED}:
        return Eligibility(False, "already_returned", "The order is in the return process")
    if order_status == OrderStatus.DELIVERED:
        return Eligibility(False, "already_delivered", "A delivered order cannot be cancelled")
    return Eligibility(False, "already_shipped", "The order has shipped and cannot be cancelled")


def check_return_eligibility(
    order_status: str,
    delivered_at: datetime | None,
    is_returnable: bool,
    has_active_return: bool,
    now: datetime,
) -> Eligibility:
    """Pure rule: delivered, within 14 days of delivery, returnable, no active return."""
    if order_status != OrderStatus.DELIVERED or delivered_at is None:
        return Eligibility(False, "not_delivered", "Only delivered orders can be returned")
    if not is_returnable:
        return Eligibility(False, "not_returnable", "This product cannot be returned")
    if has_active_return:
        return Eligibility(False, "return_exists", "A return is already open for this item")
    if now - delivered_at > timedelta(days=RETURN_WINDOW_DAYS):
        return Eligibility(False, "window_expired", "The 14-day return window has passed")
    return Eligibility(True, "ok", "The item can be returned")
