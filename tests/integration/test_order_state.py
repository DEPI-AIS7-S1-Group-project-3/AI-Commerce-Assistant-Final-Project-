import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.enums import ActorType, OrderStatus
from ai_commerce_marketplace.core.exceptions import ConflictError
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models.order import OrderStatusHistory
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.services.order_state import (
    TRANSITIONS,
    can_transition,
    change_status,
)
from tests import factories as f

S = OrderStatus

ALLOWED = [
    (S.PENDING, S.CONFIRMED),
    (S.PENDING, S.CANCELLED),
    (S.CONFIRMED, S.SHIPPED),
    (S.CONFIRMED, S.CANCELLED),
    (S.SHIPPED, S.OUT_FOR_DELIVERY),
    (S.OUT_FOR_DELIVERY, S.DELIVERED),
    (S.DELIVERED, S.RETURN_REQUESTED),
    (S.RETURN_REQUESTED, S.RETURNED),
]

FORBIDDEN = [
    (S.DELIVERED, S.PENDING),
    (S.PENDING, S.DELIVERED),
    (S.PENDING, S.SHIPPED),
    (S.SHIPPED, S.CANCELLED),
    (S.DELIVERED, S.CANCELLED),
    (S.CANCELLED, S.PENDING),
    (S.CANCELLED, S.CONFIRMED),
    (S.RETURNED, S.DELIVERED),
    (S.CONFIRMED, S.PENDING),
]


# ---- pure rules ----
@pytest.mark.parametrize(("a", "b"), ALLOWED)
def test_allowed_transitions(a, b):
    assert can_transition(a, b)


@pytest.mark.parametrize(("a", "b"), FORBIDDEN)
def test_forbidden_transitions(a, b):
    assert not can_transition(a, b)


def test_terminal_states_have_no_exit():
    assert TRANSITIONS[S.CANCELLED] == frozenset()
    assert TRANSITIONS[S.RETURNED] == frozenset()


def test_unknown_state_has_no_transitions():
    assert not can_transition("nonsense", S.PENDING)


def test_every_status_is_covered():
    assert set(TRANSITIONS) == {s.value for s in OrderStatus}


# ---- change_status ----
def test_change_status_writes_history(session):
    seller_user = f.make_user(session, role="seller")
    order = f.make_order(session)
    change_status(
        session,
        order,
        S.CONFIRMED,
        actor_type=ActorType.SELLER,
        actor_user_id=seller_user.id,
        note="ok",
    )
    assert order.status == "confirmed"
    rows = session.scalars(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].from_status == "pending"
    assert rows[0].to_status == "confirmed"
    assert rows[0].actor_type == "seller"
    assert rows[0].actor_user_id == seller_user.id
    assert rows[0].note == "ok"


def test_change_status_sets_cancelled_at(session):
    order = f.make_order(session)
    change_status(
        session, order, S.CANCELLED, actor_type=ActorType.CUSTOMER, reason_code="customer_request"
    )
    assert order.cancelled_at is not None
    assert order.cancel_reason_code == "customer_request"


def test_change_status_sets_delivered_at_and_survives_db_checks(session):
    order = f.make_order(session, status="out_for_delivery")
    change_status(session, order, S.DELIVERED, actor_type=ActorType.SELLER)
    assert order.delivered_at is not None
    # moving on from delivered keeps delivered_at (DB constraint requires it)
    change_status(session, order, S.RETURN_REQUESTED, actor_type=ActorType.CUSTOMER)
    assert order.delivered_at is not None


def test_full_happy_chain(session):
    order = f.make_order(session)
    for target in (S.CONFIRMED, S.SHIPPED, S.OUT_FOR_DELIVERY, S.DELIVERED):
        change_status(session, order, target, actor_type=ActorType.SYSTEM)
    assert order.status == "delivered"
    rows = session.scalars(
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.id)
    ).all()
    assert [r.to_status for r in rows] == ["confirmed", "shipped", "out_for_delivery", "delivered"]


def test_invalid_transition_rejected_and_state_unchanged(session):
    order = f.make_order(session)  # a valid pending order
    change_status(session, order, S.CONFIRMED, actor_type=ActorType.SELLER)
    change_status(session, order, S.SHIPPED, actor_type=ActorType.SELLER)
    change_status(session, order, S.OUT_FOR_DELIVERY, actor_type=ActorType.SELLER)
    change_status(session, order, S.DELIVERED, actor_type=ActorType.SELLER)

    with pytest.raises(ConflictError) as e:
        change_status(session, order, S.PENDING, actor_type=ActorType.SYSTEM)

    assert e.value.code == "invalid_transition"
    assert order.status == "delivered"
    rows = session.scalars(
        select(OrderStatusHistory).where(OrderStatusHistory.order_id == order.id)
    ).all()
    assert len(rows) == 4  # only the 4 valid transitions were recorded


# ---- customer endpoints ----
@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app, raise_server_exceptions=False)


def _h(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def test_list_shows_only_my_orders(client, session):
    me = f.make_user(session)
    other = f.make_user(session)
    mine = f.make_order(session, customer_id=me.id)
    f.make_order(session, customer_id=other.id)
    r = client.get("/orders", headers=_h(me))
    assert r.status_code == 200
    assert [o["id"] for o in r.json()] == [mine.id]


def test_list_empty(client, session):
    me = f.make_user(session)
    assert client.get("/orders", headers=_h(me)).json() == []


def test_list_newest_first(client, session):
    me = f.make_user(session)
    first = f.make_order(session, customer_id=me.id)
    second = f.make_order(session, customer_id=me.id)
    ids = [o["id"] for o in client.get("/orders", headers=_h(me)).json()]
    assert ids == [second.id, first.id]


def test_detail_includes_items_and_timeline(client, session):
    me = f.make_user(session)
    order = f.make_order(session, customer_id=me.id)
    f.make_order_item(session, order=order, qty=2)
    change_status(session, order, S.CONFIRMED, actor_type=ActorType.SELLER)
    change_status(session, order, S.SHIPPED, actor_type=ActorType.SELLER)

    r = client.get(f"/orders/{order.id}", headers=_h(me))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "shipped"
    assert len(body["items"]) == 1
    assert body["items"][0]["qty"] == 2
    assert [t["to_status"] for t in body["timeline"]] == ["confirmed", "shipped"]
    assert body["timeline"][0]["from_status"] == "pending"


def test_other_customers_order_is_404(client, session):
    me = f.make_user(session)
    other = f.make_user(session)
    theirs = f.make_order(session, customer_id=other.id)
    r = client.get(f"/orders/{theirs.id}", headers=_h(me))
    assert r.status_code == 404
    assert r.json()["code"] == "order_not_found"


def test_unknown_order_404(client, session):
    me = f.make_user(session)
    assert client.get("/orders/999999", headers=_h(me)).status_code == 404


def test_orders_require_login(client):
    assert client.get("/orders").status_code == 401
    assert client.get("/orders/10001").status_code == 401
