from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, inspect

from ai_commerce_marketplace.database.models import Product
from tests import factories as f

NOW = datetime.now(timezone.utc)


# ───────────── الـ schema ─────────────
def test_all_15_tables_exist(session):
    names = set(inspect(session.connection()).get_table_names())
    expected = {
        "users", "addresses", "sellers", "categories", "brands", "products",
        "product_images", "carts", "cart_items", "orders", "order_items",
        "order_status_history", "returns", "reviews", "policies",
    }
    assert expected <= names


# ───────────── CHECK: users ─────────────
@pytest.mark.parametrize("phone", ["0123", "02012345678", "010123456789", "abc"])
def test_user_rejects_bad_phone(session, rejected, phone):
    with rejected():
        f.make_user(session, phone=phone)


def test_user_rejects_bad_role_and_blank_name(session, rejected):
    with rejected():
        f.make_user(session, role="admin")
    with rejected():
        f.make_user(session, full_name="   ")


# ───────────── CHECK: products ─────────────
def test_valid_product_is_accepted(session):
    assert f.make_product(session).id is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"price_egp": Decimal("0")},
        {"price_egp": Decimal("-5")},
        {"stock_qty": -1},
        {"price_egp": Decimal("100"), "old_price_egp": Decimal("100")},
        {"price_egp": Decimal("100"), "old_price_egp": Decimal("90")},
        {"warranty_months": 61},
        {"rating_avg": Decimal("6")},
        {"specs": [1, 2]},
    ],
    ids=["price_zero", "price_negative", "stock_negative", "old_eq_price",
         "old_lt_price", "warranty_61", "rating_avg_6", "specs_not_object"],
)
def test_product_checks_reject(session, rejected, overrides):
    with rejected():
        f.make_product(session, **overrides)


# ───────────── CHECK: orders ─────────────
def test_valid_orders_are_accepted(session):
    f.make_order(session)
    f.make_order(session, status="cancelled", cancelled_at=NOW)
    f.make_order(session, status="delivered", delivered_at=NOW + timedelta(days=1))


@pytest.mark.parametrize(
    "overrides",
    [
        {"total_egp": Decimal("1")},
        {"status": "cancelled"},
        {"status": "delivered"},
        {"status": "unknown"},
        {"cancelled_at": NOW},
        {"shipping_address": [1, 2]},
        {"shipping_fee_egp": Decimal("-1"), "total_egp": Decimal("999")},
        {"status": "delivered", "delivered_at": NOW - timedelta(days=30)},
    ],
    ids=["total_mismatch", "cancelled_no_date", "delivered_no_date", "bad_status",
         "date_without_cancelled_status", "address_not_object", "negative_fee",
         "delivered_before_created"],
)
def test_order_checks_reject(session, rejected, overrides):
    with rejected():
        f.make_order(session, **overrides)


# ───────────── CHECK: reviews & order_items ─────────────
@pytest.mark.parametrize("rating", [0, 6])
def test_review_rating_must_be_1_to_5(session, rejected, rating):
    item = f.make_order_item(session)
    with rejected():
        f.make_review(session, item, rating=rating)


def test_order_item_rejects_bad_qty_and_price(session, rejected):
    order = f.make_order(session)
    product = f.make_product(session)
    with rejected():
        f.make_order_item(session, order, product, qty=0)
    with rejected():
        f.make_order_item(session, order, product, unit_price=Decimal("0"))


# ───────────── UNIQUE ─────────────
def test_email_unique_case_insensitive(session, rejected):
    f.make_user(session, email="Ali@Example.com")
    with rejected():
        f.make_user(session, email="ali@example.com")


def test_one_default_address_per_user(session, rejected):
    user = f.make_user(session)
    f.make_address(session, user, is_default=True)
    f.make_address(session, user, is_default=False)  # عادي
    f.make_address(session, f.make_user(session), is_default=True)  # مستخدم تاني عادي
    with rejected():
        f.make_address(session, user, is_default=True)


def test_one_review_per_order_item(session, rejected):
    item = f.make_order_item(session)
    f.make_review(session, item)
    with rejected():
        f.make_review(session, item, rating=3)


def test_one_active_return_per_item(session, rejected):
    item = f.make_order_item(session, qty=2)
    first = f.make_return(session, item)
    with rejected():
        f.make_return(session, item)
    first.status = "rejected"  # بعد الرفض يقدر يطلب تاني
    session.flush()
    f.make_return(session, item)


def test_one_current_policy_per_slug(session, rejected):
    f.make_policy(session, version="v1", is_current=True)
    f.make_policy(session, version="v0", is_current=False)  # قديمة عادي
    with rejected():
        f.make_policy(session, version="v2", is_current=True)
    with rejected():
        f.make_policy(session, version="v1", is_current=False)  # (slug, version) مكرر


# ───────────── FK ─────────────
def test_cannot_delete_product_with_orders(session, rejected):
    item = f.make_order_item(session)
    with rejected():
        session.execute(delete(Product).where(Product.id == item.product_id))


def test_can_delete_product_without_orders(session):
    product = f.make_product(session)
    session.execute(delete(Product).where(Product.id == product.id))
    session.flush()


# ───────────── السلوك الخاص بالـ DB ─────────────
def test_line_total_is_computed(session):
    item = f.make_order_item(session, qty=3, unit_price=Decimal("100.00"))
    session.refresh(item)
    assert item.line_total_egp == Decimal("300.00")


def test_order_ids_start_at_10001(session):
    assert f.make_order(session).id >= 10001