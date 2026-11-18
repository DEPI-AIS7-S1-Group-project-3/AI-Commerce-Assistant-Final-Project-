from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models import User
from ai_commerce_marketplace.database.models.order import OrderStatusHistory
from ai_commerce_marketplace.database.session import get_session
from tests import factories as f


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


@pytest.fixture
def seller(session):
    return f.make_seller(session)


@pytest.fixture
def seller_user(session, seller):
    return session.get(User, seller.user_id)


def _order(session, seller, status="pending", days_ago=1, price="1000.00", qty=1, **kw):
    o = f.make_order(
        session,
        seller_id=seller.id,
        status=status,
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
        **kw,
    )
    f.make_order_item(session, order=o, qty=qty, unit_price=Decimal(price))
    return o


def _move(client, user, order, to_status):
    return client.post(
        f"/seller/orders/{order.id}/status", json={"to_status": to_status}, headers=_h(user)
    )


# ---- access ----
def test_seller_routes_need_a_seller_login(client, session):
    customer = f.make_user(session)
    assert client.get("/seller/dashboard").status_code == 401
    assert client.get("/seller/dashboard", headers=_h(customer)).status_code == 403
    assert client.get("/seller/orders", headers=_h(customer)).status_code == 403


# ---- dashboard ----
def test_dashboard_numbers_and_daily_series(client, session, seller, seller_user):
    _order(session, seller, days_ago=1, price="1000.00", qty=2)  # 2000
    _order(session, seller, days_ago=3, price="500.00")  # 500
    cancelled_at = datetime.now(UTC) - timedelta(days=1)
    _order(session, seller, "cancelled", 2, "9999.00", cancelled_at=cancelled_at)  # not counted
    _order(session, f.make_seller(session), days_ago=1, price="7777.00")  # other seller
    session.flush()

    r = client.get("/seller/dashboard?days=30", headers=_h(seller_user))

    assert r.status_code == 200, r.text
    body = r.json()
    assert Decimal(body["kpis"]["revenue"]) == Decimal("2500.00")
    assert body["kpis"]["orders_count"] == 2
    assert body["store_name"] == seller.store_name
    assert len(body["daily"]) in (30, 31)  # Cairo days covered by the 30-day window
    assert sum(Decimal(d["revenue"]) for d in body["daily"]) == Decimal("2500.00")
    assert body["pending_actions"] == 2


def test_dashboard_low_stock(client, session, seller, seller_user):
    low = f.make_product(session, seller_id=seller.id, stock_qty=2)
    f.make_product(session, seller_id=seller.id, stock_qty=50)
    r = client.get("/seller/dashboard", headers=_h(seller_user))
    assert [p["product_id"] for p in r.json()["low_stock"]] == [low.id]


def test_dashboard_days_validation(client, seller_user):
    assert client.get("/seller/dashboard?days=3", headers=_h(seller_user)).status_code == 422


# ---- orders ----
def test_list_orders_only_own_and_filter(client, session, seller, seller_user):
    mine = _order(session, seller, status="confirmed")
    _order(session, seller, status="pending")
    _order(session, f.make_seller(session))

    all_ids = [o["id"] for o in client.get("/seller/orders", headers=_h(seller_user)).json()]
    assert mine.id in all_ids and len(all_ids) == 2

    confirmed = client.get("/seller/orders?status=confirmed", headers=_h(seller_user)).json()
    assert [o["id"] for o in confirmed] == [mine.id]
    assert confirmed[0]["next_status"] == "shipped"


def test_advance_one_step_writes_history(client, session, seller, seller_user):
    o = _order(session, seller, status="pending")
    r = _move(client, seller_user, o, "confirmed")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed"
    h = session.scalars(select(OrderStatusHistory).where(OrderStatusHistory.order_id == o.id)).all()
    assert [(x.to_status, x.actor_type) for x in h][-1] == ("confirmed", "seller")


def test_cannot_skip_steps(client, session, seller, seller_user):
    o = _order(session, seller, status="pending")
    r = _move(client, seller_user, o, "shipped")
    assert r.status_code == 409
    assert r.json()["code"] == "invalid_transition"
    assert r.json()["details"]["next"] == "confirmed"


def test_cancel_is_not_a_seller_move(client, session, seller, seller_user):
    o = _order(session, seller, status="pending")
    r = _move(client, seller_user, o, "cancelled")
    assert r.status_code == 422


def test_delivered_sets_date_and_cod_paid(client, session, seller, seller_user):
    o = _order(session, seller, status="out_for_delivery", payment_method="cod")
    r = _move(client, seller_user, o, "delivered")
    assert r.status_code == 200, r.text
    assert r.json()["delivered_at"] is not None
    assert r.json()["payment_status"] == "paid"
    assert r.json()["next_status"] is None


def test_other_sellers_order_looks_missing(client, session, seller_user):
    other = _order(session, f.make_seller(session), status="pending")
    r = _move(client, seller_user, other, "confirmed")
    assert r.status_code == 404
