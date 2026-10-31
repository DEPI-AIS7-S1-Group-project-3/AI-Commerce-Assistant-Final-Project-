import itertools
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai_commerce_marketplace.database.models import (
    Address,
    Brand,
    Category,
    Order,
    OrderItem,
    Policy,
    Product,
    Return,
    Review,
    Seller,
    User,
)

_counter = itertools.count(1)


def _n() -> int:
    return next(_counter)


def _save(session, obj):
    session.add(obj)
    session.flush()
    return obj


def make_user(session, **kw):
    n = _n()
    data = dict(
        role="customer",
        full_name=f"User {n}",
        email=f"user{n}@example.com",
        phone="01012345678",
        password_hash="not-a-real-hash",
    )
    return _save(session, User(**{**data, **kw}))


def make_seller(session, **kw):
    n = _n()
    user = make_user(session, role="seller")
    data = dict(user_id=user.id, store_name=f"Store {n}")
    return _save(session, Seller(**{**data, **kw}))


def make_category(session, **kw):
    n = _n()
    data = dict(slug=f"cat-{n}", name_ar="فئة", name_en=f"Category {n}", spec_kind="mobile")
    return _save(session, Category(**{**data, **kw}))


def make_brand(session, **kw):
    n = _n()
    data = dict(slug=f"brand-{n}", name=f"Brand {n}")
    return _save(session, Brand(**{**data, **kw}))


def make_product(session, **kw):
    n = _n()
    seller_id = kw.pop("seller_id", None) or make_seller(session).id
    category_id = kw.pop("category_id", None) or make_category(session).id
    brand_id = kw.pop("brand_id", None) or make_brand(session).id
    data = dict(
        seller_id=seller_id,
        category_id=category_id,
        brand_id=brand_id,
        sku=f"SKU-{n}",
        title_ar="منتج تجريبي",
        price_egp=Decimal("1000.00"),
        stock_qty=10,
        specs={"ram_gb": 8},
    )
    return _save(session, Product(**{**data, **kw}))


def make_address(session, user, **kw):
    data = dict(
        user_id=user.id,
        recipient_name="عميل تجريبي",
        phone="01012345678",
        governorate="القاهرة",
        city="مدينة نصر",
        street_address="شارع تجريبي 1",
    )
    return _save(session, Address(**{**data, **kw}))


def make_order(session, **kw):
    customer_id = kw.pop("customer_id", None) or make_user(session).id
    seller_id = kw.pop("seller_id", None) or make_seller(session).id
    data = dict(
        checkout_group_id=uuid.uuid4(),
        customer_id=customer_id,
        seller_id=seller_id,
        status="pending",
        payment_method="cod",
        shipping_address={"recipient_name": "عميل", "governorate": "القاهرة"},
        subtotal_egp=Decimal("1000.00"),
        shipping_fee_egp=Decimal("60.00"),
        total_egp=Decimal("1060.00"),
        expected_delivery_at=datetime.now(UTC) + timedelta(days=2),
    )
    return _save(session, Order(**{**data, **kw}))


def make_order_item(session, order=None, product=None, qty=1, unit_price=Decimal("100.00"), **kw):
    order = order or make_order(session)
    product = product or make_product(session)
    data = dict(
        order_id=order.id,
        product_id=product.id,
        product_title_snapshot=product.title_ar,
        qty=qty,
        unit_price_egp=unit_price,
    )
    return _save(session, OrderItem(**{**data, **kw}))


def make_review(session, item, **kw):
    order = session.get(Order, item.order_id)
    data = dict(
        product_id=item.product_id,
        customer_id=order.customer_id,
        order_item_id=item.id,
        rating=5,
        body="ممتاز",
    )
    return _save(session, Review(**{**data, **kw}))


def make_return(session, item, **kw):
    order = session.get(Order, item.order_id)
    data = dict(
        order_item_id=item.id,
        requested_by=order.customer_id,
        qty=1,
        reason_code="defective",
        status="requested",
    )
    return _save(session, Return(**{**data, **kw}))


def make_policy(session, **kw):
    data = dict(
        slug="returns",
        category="returns",
        title_ar="سياسة الإرجاع",
        body_md="## 1. نص تجريبي",
        version="2026-10-01",
    )
    return _save(session, Policy(**{**data, **kw}))
