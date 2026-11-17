from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from ai_commerce_marketplace.core.enums import PaymentMethod, ReturnReason


class CheckoutIn(BaseModel):
    address_id: int
    payment_method: PaymentMethod


class OrderItemOut(BaseModel):
    id: int  # order item id, used by POST /orders/{order_id}/items/{id}/return
    product_id: int
    title: str
    qty: int
    unit_price_egp: Decimal
    line_total_egp: Decimal
    is_returnable: bool
    return_status: str | None  # latest return for this item (requested/approved/...), or None
    can_return: bool  # computed with order_rules.check_return_eligibility
    return_block: str | None  # why can_return is False (not_delivered, window_expired, ...)


class OrderOut(BaseModel):
    id: int
    checkout_group_id: str  # orders from the same checkout share it (one per seller)
    seller_id: int
    seller_name: str
    status: str
    payment_method: str
    payment_status: str
    shipping_address: dict[str, Any]
    subtotal_egp: Decimal
    shipping_fee_egp: Decimal
    total_egp: Decimal
    expected_delivery_at: datetime
    delivered_at: datetime | None
    created_at: datetime
    can_cancel: bool  # computed with order_rules.check_cancel_eligibility
    cancel_block: str | None  # why can_cancel is False (already_shipped, ...)
    items: list[OrderItemOut]


class CheckoutOut(BaseModel):
    checkout_group_id: str
    orders: list[OrderOut]


class TimelineEntry(BaseModel):
    from_status: str | None
    to_status: str
    actor_type: str
    created_at: datetime


class OrderDetailOut(OrderOut):
    timeline: list[TimelineEntry]


class ReturnIn(BaseModel):
    reason_code: ReturnReason
    reason_text: str | None = Field(default=None, max_length=500)


class ReturnOut(BaseModel):
    id: int
    order_item_id: int
    qty: int
    reason_code: str
    status: str
