from datetime import UTC, datetime, timedelta

import pytest

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.services import order_support as svc
from tests import factories as f

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


# ---- add_months (pure) ----
@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (datetime(2026, 1, 31, tzinfo=UTC), 1, datetime(2026, 2, 28, tzinfo=UTC)),
        (datetime(2028, 1, 31, tzinfo=UTC), 1, datetime(2028, 2, 29, tzinfo=UTC)),
        (datetime(2026, 11, 18, tzinfo=UTC), 12, datetime(2027, 11, 18, tzinfo=UTC)),
        (datetime(2026, 11, 18, tzinfo=UTC), 14, datetime(2028, 1, 18, tzinfo=UTC)),
        (datetime(2026, 5, 10, tzinfo=UTC), 0, datetime(2026, 5, 10, tzinfo=UTC)),
    ],
)
def test_add_months(start, months, expected):
    assert svc.add_months(start, months) == expected


def _order_with_item(session, *, warranty, status="delivered", delivered_days_ago=10):
    user = f.make_user(session)
    product = f.make_product(session, warranty_months=warranty)
    delivered = NOW - timedelta(days=delivered_days_ago) if status == "delivered" else None
    # the DB requires created_at <= delivered_at, so back-date the order too
    created = (delivered or NOW) - timedelta(days=3)
    order = f.make_order(
        session, customer_id=user.id, status=status, delivered_at=delivered, created_at=created
    )
    item = f.make_order_item(session, order=order, product=product)
    return user, order, item


# ---- warranty ----
def test_warranty_active_with_days_left(session):
    user, order, _ = _order_with_item(session, warranty=12, delivered_days_ago=10)
    out = svc.order_warranty(session, user.id, order.id, now=NOW)
    (item,) = out["items"]
    assert item["state"] == "active"
    assert item["starts_at"] == order.delivered_at
    assert item["ends_at"] == svc.add_months(order.delivered_at, 12)
    assert item["days_left"] == (item["ends_at"] - NOW).days


def test_warranty_expired(session):
    user, order, _ = _order_with_item(session, warranty=1, delivered_days_ago=60)
    (item,) = svc.order_warranty(session, user.id, order.id, now=NOW)["items"]
    assert item["state"] == "expired" and item["days_left"] == 0


def test_warranty_not_started_before_delivery(session):
    user, order, _ = _order_with_item(session, warranty=12, status="shipped")
    (item,) = svc.order_warranty(session, user.id, order.id, now=NOW)["items"]
    assert item["state"] == "not_started"
    assert item["ends_at"] is None and item["days_left"] is None


def test_product_without_warranty(session):
    user, order, _ = _order_with_item(session, warranty=0)
    (item,) = svc.order_warranty(session, user.id, order.id, now=NOW)["items"]
    assert item["state"] == "no_warranty"


def test_warranty_of_another_customers_order_is_not_found(session):
    _, order, _ = _order_with_item(session, warranty=12)
    stranger = f.make_user(session)
    with pytest.raises(NotFoundError) as e:
        svc.order_warranty(session, stranger.id, order.id, now=NOW)
    assert e.value.code == "order_not_found"


def test_warranty_of_missing_order_is_not_found(session):
    user = f.make_user(session)
    with pytest.raises(NotFoundError):
        svc.order_warranty(session, user.id, 999999, now=NOW)


# ---- returns ----
def test_returns_empty_when_none_requested(session):
    user, order, _ = _order_with_item(session, warranty=12)
    out = svc.order_returns(session, user.id, order.id)
    assert out["returns"] == [] and out["order_id"] == order.id


def test_returns_lists_requests_with_status(session):
    user, order, item = _order_with_item(session, warranty=12)
    f.make_return(session, item, status="approved", reason_code="defective")
    (r,) = svc.order_returns(session, user.id, order.id)["returns"]
    assert r["item_id"] == item.id
    assert r["status"] == "approved" and r["reason_code"] == "defective"
    assert r["title"] == item.product_title_snapshot


def test_returns_of_another_customers_order_is_not_found(session):
    _, order, item = _order_with_item(session, warranty=12)
    f.make_return(session, item)
    stranger = f.make_user(session)
    with pytest.raises(NotFoundError):
        svc.order_returns(session, stranger.id, order.id)
