from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.enums import ActorType, OrderStatus
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models.order import Order, OrderStatusHistory, Return
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.services.order_rules import (
    check_cancel_eligibility,
    check_return_eligibility,
)
from ai_commerce_marketplace.services.order_state import change_status
from tests import factories as f

S = OrderStatus
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


# ---- pure cancel rules ----
@pytest.mark.parametrize("status", [S.PENDING, S.CONFIRMED])
def test_cancel_allowed_before_shipping(status):
    assert check_cancel_eligibility(status, NOW).allowed


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (S.SHIPPED, "already_shipped"),
        (S.OUT_FOR_DELIVERY, "already_shipped"),
        (S.DELIVERED, "already_delivered"),
        (S.CANCELLED, "already_cancelled"),
        (S.RETURN_REQUESTED, "already_returned"),
        (S.RETURNED, "already_returned"),
    ],
)
def test_cancel_rejected_after_shipping(status, code):
    v = check_cancel_eligibility(status, NOW)
    assert not v.allowed
    assert v.code == code
    assert v.message


# ---- pure return rules (boundary days) ----
def _ret(delivered_days_ago, **kw):
    args = dict(
        order_status="delivered",
        delivered_at=NOW - delivered_days_ago,
        is_returnable=True,
        has_active_return=False,
        now=NOW,
    )
    return check_return_eligibility(**{**args, **kw})


def test_return_day_14_accepted():
    assert _ret(timedelta(days=14)).allowed


def test_return_day_15_rejected():
    v = _ret(timedelta(days=14, seconds=1))
    assert not v.allowed
    assert v.code == "window_expired"


def test_return_day_1_accepted():
    assert _ret(timedelta(days=1)).allowed


def test_return_not_returnable_product():
    assert _ret(timedelta(days=1), is_returnable=False).code == "not_returnable"


def test_return_existing_active_return():
    assert _ret(timedelta(days=1), has_active_return=True).code == "return_exists"


@pytest.mark.parametrize("status", ["pending", "shipped", "cancelled", "return_requested"])
def test_return_requires_delivered(status):
    assert _ret(timedelta(days=1), order_status=status).code == "not_delivered"


def test_return_without_delivery_date():
    assert _ret(timedelta(days=1), delivered_at=None).code == "not_delivered"


# ---- API ----
@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _order_with_item(session, user, product=None, qty=2):
    order = f.make_order(session, customer_id=user.id)
    product = product or f.make_product(session, stock_qty=10)
    item = f.make_order_item(session, order=order, product=product, qty=qty)
    session.commit()
    return order, item, product


def _deliver(session, order, days_ago):
    """Move an order to delivered via the state machine, then backdate it."""
    for target in (S.CONFIRMED, S.SHIPPED, S.OUT_FOR_DELIVERY, S.DELIVERED):
        change_status(session, order, target, actor_type=ActorType.SYSTEM)
    order.created_at = datetime.now(UTC) - timedelta(days=days_ago + 5)
    order.delivered_at = datetime.now(UTC) - timedelta(days=days_ago)
    session.commit()


# ---- cancel ----
def test_cancel_pending_order_restores_stock(client, session):
    user = f.make_user(session)
    order, _, product = _order_with_item(session, user, qty=3)
    assert product.stock_qty == 10

    r = client.post(f"/orders/{order.id}/cancel", headers=_h(user))
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    session.refresh(product)
    assert product.stock_qty == 13
    session.refresh(order)
    assert order.cancelled_at is not None
    assert order.cancel_reason_code == "customer_request"

    history = session.scalars(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
    ).all()
    assert [h.to_status for h in history] == ["cancelled"]
    assert history[0].actor_type == "customer"
    assert history[0].actor_user_id == user.id


def test_cancel_confirmed_order_allowed(client, session):
    user = f.make_user(session)
    order, _, _ = _order_with_item(session, user)
    change_status(session, order, S.CONFIRMED, actor_type=ActorType.SELLER)
    assert client.post(f"/orders/{order.id}/cancel", headers=_h(user)).status_code == 200


def test_cancel_after_shipping_rejected_and_stock_unchanged(client, session):
    user = f.make_user(session)
    order, _, product = _order_with_item(session, user)
    for t in (S.CONFIRMED, S.SHIPPED):
        change_status(session, order, t, actor_type=ActorType.SELLER)
    session.commit()
    r = client.post(f"/orders/{order.id}/cancel", headers=_h(user))
    assert r.status_code == 409
    assert r.json()["code"] == "already_shipped"
    assert r.json()["message"]

    session.expire_all()
    assert session.get(Order, order.id).status == "shipped"
    assert product.stock_qty == 10


def test_cancel_twice_rejected_and_stock_restored_once(client, session):
    user = f.make_user(session)
    order, _, product = _order_with_item(session, user, qty=2)
    assert client.post(f"/orders/{order.id}/cancel", headers=_h(user)).status_code == 200
    r = client.post(f"/orders/{order.id}/cancel", headers=_h(user))
    assert r.status_code == 409
    assert r.json()["code"] == "already_cancelled"
    session.refresh(product)
    assert product.stock_qty == 12  # restored once, not twice


def test_cannot_cancel_other_customers_order(client, session):
    owner = f.make_user(session)
    other = f.make_user(session)
    order, _, product = _order_with_item(session, owner)
    r = client.post(f"/orders/{order.id}/cancel", headers=_h(other))
    assert r.status_code == 404
    session.expire_all()
    assert session.get(Order, order.id).status == "pending"
    assert product.stock_qty == 10


def test_cancel_requires_login(client):
    assert client.post("/orders/10001/cancel").status_code == 401


# ---- return ----
def _return(client, user, order, item, reason="defective"):
    return client.post(
        f"/orders/{order.id}/items/{item.id}/return",
        json={"reason_code": reason, "reason_text": "screen flickers"},
        headers=_h(user),
    )


def test_return_within_window_creates_return_row(client, session):
    user = f.make_user(session)
    order, item, _ = _order_with_item(session, user)
    _deliver(session, order, days_ago=3)

    r = _return(client, user, order, item)
    assert r.status_code == 201
    assert r.json()["status"] == "requested"
    assert r.json()["qty"] == item.qty

    session.expire_all()
    assert session.get(Order, order.id).status == "return_requested"
    rows = session.scalars(select(Return).where(Return.order_item_id == item.id)).all()
    assert len(rows) == 1
    assert rows[0].requested_by == user.id


def test_return_after_window_rejected(client, session):
    user = f.make_user(session)
    order, item, _ = _order_with_item(session, user)
    _deliver(session, order, days_ago=15)

    r = _return(client, user, order, item)
    assert r.status_code == 409
    assert r.json()["code"] == "window_expired"
    count = session.scalar(select(func.count()).select_from(Return))
    assert count == 0
    session.expire_all()
    assert session.get(Order, order.id).status == "delivered"


def test_return_non_returnable_product_rejected(client, session):
    user = f.make_user(session)
    product = f.make_product(session, is_returnable=False)
    order, item, _ = _order_with_item(session, user, product=product)
    _deliver(session, order, days_ago=1)
    r = _return(client, user, order, item)
    assert r.status_code == 409
    assert r.json()["code"] == "not_returnable"


def test_return_before_delivery_rejected(client, session):
    user = f.make_user(session)
    order, item, _ = _order_with_item(session, user)
    r = _return(client, user, order, item)
    assert r.status_code == 409
    assert r.json()["code"] == "not_delivered"


def test_second_return_for_same_item_rejected(client, session):
    user = f.make_user(session)
    order, item, _ = _order_with_item(session, user)
    _deliver(session, order, days_ago=2)
    assert _return(client, user, order, item).status_code == 201
    r = _return(client, user, order, item)
    assert r.status_code == 409  # order is now return_requested


def test_return_bad_reason_422(client, session):
    user = f.make_user(session)
    order, item, _ = _order_with_item(session, user)
    _deliver(session, order, days_ago=2)
    assert _return(client, user, order, item, reason="because").status_code == 422


def test_cannot_return_other_customers_item(client, session):
    owner = f.make_user(session)
    other = f.make_user(session)
    order, item, _ = _order_with_item(session, owner)
    _deliver(session, order, days_ago=2)
    assert _return(client, other, order, item).status_code == 404


def test_item_from_another_order_404(client, session):
    user = f.make_user(session)
    order, _, _ = _order_with_item(session, user)
    _, other_item, _ = _order_with_item(session, user)
    _deliver(session, order, days_ago=2)
    assert _return(client, user, order, other_item).status_code == 404


def test_return_requires_login(client):
    assert client.post("/orders/1/items/1/return", json={"reason_code": "other"}).status_code == 401
