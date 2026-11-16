from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.order import OrderItem
from ai_commerce_marketplace.services import seller_analytics as sa
from ai_commerce_marketplace.services.seller_analytics import Period
from tests import factories as f

T0 = datetime(2026, 10, 1, tzinfo=UTC)
P = Period(T0, T0 + timedelta(days=30))


def _order(session, seller, product, qty, price, status="pending", days=1, **kw):
    created = T0 + timedelta(days=days)
    extra = {}
    if status in ("delivered", "returned"):
        extra["delivered_at"] = created + timedelta(days=1)
    if status == "cancelled":
        extra["cancelled_at"] = created + timedelta(hours=1)
    o = f.make_order(
        session,
        seller_id=seller.id,
        status=status,
        created_at=created,
        subtotal_egp=price * qty,
        shipping_fee_egp=Decimal("60.00"),
        total_egp=price * qty + Decimal("60.00"),
        **extra,
        **kw,
    )
    f.make_order_item(session, order=o, product=product, qty=qty, unit_price=price)
    return o


@pytest.fixture
def seller(session):
    return f.make_seller(session)


def test_revenue_excludes_shipping_cancelled_and_returned(session, seller):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 2, Decimal("100.00"))  # 200
    _order(session, seller, p, 1, Decimal("50.00"), status="delivered")  # 50
    _order(session, seller, p, 5, Decimal("100.00"), status="cancelled")  # excluded
    _order(session, seller, p, 4, Decimal("100.00"), status="returned")  # excluded
    s = sa.sales_summary(session, seller.id, P)
    assert s["revenue"] == Decimal("250.00")
    assert s["units_sold"] == 3
    assert s["orders_count"] == 2
    assert s["aov"] == Decimal("125.00")


def test_return_requested_is_counted(session, seller):
    p = f.make_product(session, seller_id=seller.id)
    o = _order(session, seller, p, 1, Decimal("80.00"), status="delivered")
    o.status = "return_requested"
    session.flush()
    assert sa.sales_summary(session, seller.id, P)["revenue"] == Decimal("80.00")


def test_period_start_inclusive_end_exclusive(session, seller):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 1, Decimal("10.00"), days=0)  # at start: in
    _order(session, seller, p, 1, Decimal("20.00"), days=30)  # at end: out
    assert sa.sales_summary(session, seller.id, P)["revenue"] == Decimal("10.00")


def test_empty_period_returns_zeros(session, seller):
    s = sa.sales_summary(session, seller.id, P)
    assert (s["revenue"], s["units_sold"], s["orders_count"], s["aov"]) == (
        Decimal("0.00"),
        0,
        0,
        Decimal("0.00"),
    )


def test_compare_periods_with_change(session, seller):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 1, Decimal("100.00"), days=1)
    _order(session, seller, p, 1, Decimal("150.00"), days=40)
    b = Period(T0 + timedelta(days=30), T0 + timedelta(days=60))
    c = sa.compare_periods(session, seller.id, P, b)
    assert c["revenue"]["delta"] == Decimal("50.00")
    assert c["revenue"]["change_pct"] == Decimal("50.0")


def test_compare_with_zero_baseline_has_null_pct(session, seller):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 1, Decimal("100.00"), days=40)
    b = Period(T0 + timedelta(days=30), T0 + timedelta(days=60))
    c = sa.compare_periods(session, seller.id, P, b)
    assert c["revenue"]["change_pct"] is None
    assert c["revenue"]["delta"] == Decimal("100.00")


def test_top_products_order(session, seller):
    a = f.make_product(session, seller_id=seller.id)
    b = f.make_product(session, seller_id=seller.id)
    _order(session, seller, a, 1, Decimal("10.00"))
    _order(session, seller, b, 5, Decimal("10.00"))
    top = sa.top_products(session, seller.id, P, limit=2)
    assert [t["product_id"] for t in top] == [b.id, a.id]
    worst = sa.top_products(session, seller.id, P, limit=1, worst=True)
    assert worst[0]["product_id"] == a.id


def test_low_stock_only_active_and_sorted(session, seller):
    zero = f.make_product(session, seller_id=seller.id, stock_qty=0)
    low = f.make_product(session, seller_id=seller.id, stock_qty=3)
    f.make_product(session, seller_id=seller.id, stock_qty=50)
    f.make_product(session, seller_id=seller.id, stock_qty=1, is_active=False)
    res = sa.low_stock_products(session, seller.id, threshold=5)
    assert [r["product_id"] for r in res] == [zero.id, low.id]


def test_orders_by_status(session, seller):
    p = f.make_product(session, seller_id=seller.id)
    _order(session, seller, p, 1, Decimal("10.00"))
    _order(session, seller, p, 1, Decimal("10.00"))
    _order(session, seller, p, 1, Decimal("10.00"), status="cancelled")
    assert sa.orders_by_status(session, seller.id, P) == {"pending": 2, "cancelled": 1}


def test_returns_report_skips_rejected(session, seller):
    p1 = f.make_product(session, seller_id=seller.id)
    p2 = f.make_product(session, seller_id=seller.id)
    o = _order(session, seller, p1, 1, Decimal("10.00"), status="delivered")
    item1 = session.scalar(select(OrderItem).where(OrderItem.order_id == o.id))
    item2 = f.make_order_item(session, order=o, product=p2, qty=1)
    f.make_return(session, item1, reason_code="defective")
    f.make_return(session, item2, reason_code="other", status="rejected")
    r = sa.returns_report(session, seller.id, P)
    assert r == {"total_returns": 1, "by_reason": {"defective": 1}}


def test_isolation_between_sellers(session, seller):
    other = f.make_seller(session)
    mine = f.make_product(session, seller_id=seller.id)
    theirs = f.make_product(session, seller_id=other.id)
    _order(session, seller, mine, 1, Decimal("10.00"))
    _order(session, other, theirs, 9, Decimal("999.00"))
    assert sa.sales_summary(session, seller.id, P)["revenue"] == Decimal("10.00")
    with pytest.raises(NotFoundError):
        sa.product_reviews(session, seller.id, theirs.id)
    assert all(r["product_id"] != theirs.id for r in sa.low_stock_products(session, seller.id, 999))


def test_seller_id_for_user(session, seller):
    assert sa.seller_id_for_user(session, seller.user_id) == seller.id
    with pytest.raises(NotFoundError):
        sa.seller_id_for_user(session, f.make_user(session).id)
