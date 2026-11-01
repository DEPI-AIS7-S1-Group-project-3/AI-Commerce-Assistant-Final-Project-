import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.enums import (
    ActorType,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from ai_commerce_marketplace.core.exceptions import AppError, ConflictError, NotFoundError
from ai_commerce_marketplace.database.models.cart import Cart, CartItem
from ai_commerce_marketplace.database.models.catalog import Product
from ai_commerce_marketplace.database.models.order import (
    Order,
    OrderItem,
    OrderStatusHistory,
)
from ai_commerce_marketplace.database.models.user import Address
from ai_commerce_marketplace.schemas.order import CheckoutOut, OrderItemOut, OrderOut

# Shipping rule (documented in docs/): flat fee per order, free above a threshold.
SHIPPING_FEE_EGP = Decimal("60.00")
FREE_SHIPPING_THRESHOLD_EGP = Decimal("5000.00")
DELIVERY_DAYS = 3


def shipping_fee(subtotal: Decimal) -> Decimal:
    return Decimal("0.00") if subtotal >= FREE_SHIPPING_THRESHOLD_EGP else SHIPPING_FEE_EGP


def _address_snapshot(addr: Address) -> dict[str, str | None]:
    return {
        "label": addr.label,
        "recipient_name": addr.recipient_name,
        "phone": addr.phone,
        "governorate": addr.governorate,
        "city": addr.city,
        "street_address": addr.street_address,
    }


def _to_out(order: Order, items: list[OrderItem]) -> OrderOut:
    return OrderOut(
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
        items=[
            OrderItemOut(
                product_id=i.product_id,
                title=i.product_title_snapshot,
                qty=i.qty,
                unit_price_egp=i.unit_price_egp,
                line_total_egp=i.unit_price_egp * i.qty,
            )
            for i in items
        ],
    )


def checkout(
    session: Session, user_id: int, address_id: int, payment_method: PaymentMethod
) -> CheckoutOut:
    try:
        result = _checkout(session, user_id, address_id, payment_method)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def _checkout(
    session: Session, user_id: int, address_id: int, payment_method: PaymentMethod
) -> CheckoutOut:
    addr = session.scalar(
        select(Address).where(Address.id == address_id, Address.user_id == user_id)
    )
    if addr is None:
        raise NotFoundError("Address not found", code="address_not_found")

    cart = session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        raise AppError("Your cart is empty", code="cart_empty")
    cart_items = list(session.scalars(select(CartItem).where(CartItem.cart_id == cart.id)))
    if not cart_items:
        raise AppError("Your cart is empty", code="cart_empty")
    cart_items = (
        list(session.scalars(select(CartItem).where(CartItem.cart_id == cart.id)))
        if cart is not None
        else []
    )
    if not cart_items:
        raise AppError("Your cart is empty", code="cart_empty")

    # Lock product rows in id order (prevents deadlocks between concurrent checkouts).
    product_ids = sorted(ci.product_id for ci in cart_items)
    products = {
        p.id: p
        for p in session.scalars(
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        )
    }

    # Validate every line against the locked, current data. All or nothing.
    problems = []
    for ci in cart_items:
        p = products.get(ci.product_id)
        if p is None or not p.is_active:
            problems.append({"product_id": ci.product_id, "reason": "unavailable"})
        elif ci.qty > p.stock_qty:
            problems.append(
                {
                    "product_id": ci.product_id,
                    "reason": "insufficient_stock",
                    "available": p.stock_qty,
                }
            )
    if problems:
        raise ConflictError(
            "Some items are no longer available", code="checkout_unavailable", details=problems
        )

    # One order per seller, sharing a checkout_group_id.
    by_seller: dict[int, list[CartItem]] = {}
    for ci in cart_items:
        by_seller.setdefault(products[ci.product_id].seller_id, []).append(ci)

    group_id = uuid.uuid4()
    now = datetime.now(UTC)
    paid = payment_method != PaymentMethod.COD  # wallet/card are simulated as paid
    orders_out: list[OrderOut] = []

    for seller_id in sorted(by_seller):
        lines = by_seller[seller_id]
        subtotal = sum((products[ci.product_id].price_egp * ci.qty for ci in lines), Decimal("0"))
        fee = shipping_fee(subtotal)
        order = Order(
            checkout_group_id=group_id,
            customer_id=user_id,
            seller_id=seller_id,
            status=OrderStatus.PENDING,
            payment_method=payment_method,
            payment_status=PaymentStatus.PAID if paid else PaymentStatus.PENDING,
            shipping_address=_address_snapshot(addr),
            subtotal_egp=subtotal,
            shipping_fee_egp=fee,
            total_egp=subtotal + fee,
            expected_delivery_at=now + timedelta(days=DELIVERY_DAYS),
            created_at=now,
        )
        session.add(order)
        session.flush()  # assigns order.id

        items: list[OrderItem] = []
        for ci in sorted(lines, key=lambda c: c.product_id):
            p = products[ci.product_id]
            item = OrderItem(
                order_id=order.id,
                product_id=p.id,
                product_title_snapshot=p.title_ar,
                qty=ci.qty,
                unit_price_egp=p.price_egp,  # snapshot at purchase time
            )
            session.add(item)
            items.append(item)
            p.stock_qty -= ci.qty  # row is locked; the DB CHECK forbids negative stock

        session.add(
            OrderStatusHistory(
                order_id=order.id,
                from_status=None,
                to_status=OrderStatus.PENDING,
                actor_type=ActorType.CUSTOMER,
                actor_user_id=user_id,
            )
        )
        session.flush()
        orders_out.append(_to_out(order, items))

    session.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    return CheckoutOut(checkout_group_id=str(group_id), orders=orders_out)
