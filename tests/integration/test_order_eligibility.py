"""Additions to services/order_actions used by the Order Actions Agent.

Read-only eligibility checks by order id, return qty, actor_type and cancel reason_code.
The defaults keep the website endpoints behaving exactly as before.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ai_commerce_marketplace.api.main import create_app
from ai_commerce_marketplace.core.enums import ActorType, OrderStatus, ReturnReason
from ai_commerce_marketplace.core.exceptions import ConflictError, NotFoundError
from ai_commerce_marketplace.core.security import create_access_token
from ai_commerce_marketplace.database.models.order import Order, OrderStatusHistory, Return
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.services import order_actions as svc
from ai_commerce_marketplace.services.order_state import change_status
from tests import factories as f

S = OrderStatus


def _order(session, qty=2, returnable=True):
    user = f.make_user(session)
    order = f.make_order(session, customer_id=user.id)
    product = f.make_product(session, stock_qty=10, is_returnable=returnable)
    item = f.make_order_item(session, order=order, product=product, qty=qty)
    session.commit()
    return user, order, item


def _deliver(session, order, days_ago):
    for target in (S.CONFIRMED, S.SHIPPED, S.OUT_FOR_DELIVERY, S.DELIVERED):
        change_status(session, order, target, actor_type=ActorType.SYSTEM)
    order.created_at = datetime.now(UTC) - timedelta(days=days_ago + 5)
    order.delivered_at = datetime.now(UTC) - timedelta(days=days_ago)
    session.commit()


def _history(session, order):
    return session.scalars(
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.id)
    ).all()


# ---- read-only checks ----
def test_cancel_eligibility_check_changes_nothing(session):
    user, order, _ = _order(session)
    v = svc.get_cancel_eligibility(session, user.id, order.id)
    assert (v.allowed, v.code) == (True, "ok")
    session.expire_all()
    assert session.get(Order, order.id).status == "pending"
    assert _history(session, order) == []


def test_cancel_eligibility_uses_same_rule_as_action(session):
    user, order, _ = _order(session)
    for t in (S.CONFIRMED, S.SHIPPED):
        change_status(session, order, t, actor_type=ActorType.SELLER)
    session.commit()
    v = svc.get_cancel_eligibility(session, user.id, order.id)
    assert (v.allowed, v.code) == (False, "already_shipped")
    with pytest.raises(ConflictError) as e:
        svc.cancel_order(session, user.id, order.id)
    assert e.value.code == v.code


def test_eligibility_checks_hide_other_customers_orders(session):
    _, order, item = _order(session)
    stranger = f.make_user(session)
    with pytest.raises(NotFoundError) as e:
        svc.get_cancel_eligibility(session, stranger.id, order.id)
    assert e.value.code == "order_not_found"
    with pytest.raises(NotFoundError):
        svc.get_return_eligibility(session, stranger.id, order.id, item.id)


def test_return_eligibility_check(session):
    user, order, item = _order(session, qty=2)
    _deliver(session, order, days_ago=3)
    assert svc.get_return_eligibility(session, user.id, order.id, item.id).allowed
    assert svc.get_return_eligibility(session, user.id, order.id, item.id, qty=1).allowed
    session.expire_all()
    assert session.scalars(select(Return)).all() == []


@pytest.mark.parametrize("qty", [0, 3])
def test_return_eligibility_rejects_bad_qty(session, qty):
    user, order, item = _order(session, qty=2)
    _deliver(session, order, days_ago=3)
    v = svc.get_return_eligibility(session, user.id, order.id, item.id, qty=qty)
    assert (v.allowed, v.code) == (False, "invalid_qty")


def test_return_rules_come_before_qty(session):
    user, order, item = _order(session, qty=2)
    _deliver(session, order, days_ago=20)
    v = svc.get_return_eligibility(session, user.id, order.id, item.id, qty=5)
    assert v.code == "window_expired"


def test_return_eligibility_item_of_other_order(session):
    user, order, _ = _order(session)
    other_order = f.make_order(session, customer_id=user.id)
    other_item = f.make_order_item(session, order=other_order)
    with pytest.raises(NotFoundError) as e:
        svc.get_return_eligibility(session, user.id, order.id, other_item.id)
    assert e.value.code == "order_item_not_found"


# ---- new parameters ----
def test_cancel_with_agent_actor_and_reason(session):
    user, order, _ = _order(session)
    svc.cancel_order(
        session, user.id, order.id, actor_type=ActorType.AGENT, reason_code="late_delivery"
    )
    session.expire_all()
    assert session.get(Order, order.id).cancel_reason_code == "late_delivery"
    h = _history(session, order)[-1]
    assert (h.to_status, h.actor_type, h.reason_code) == ("cancelled", "agent", "late_delivery")
    assert h.actor_user_id == user.id


def test_partial_return_qty_and_agent_actor(session):
    user, order, item = _order(session, qty=3)
    _deliver(session, order, days_ago=2)
    ret = svc.request_return(
        session,
        user.id,
        order.id,
        item.id,
        ReturnReason.DEFECTIVE,
        None,
        qty=2,
        actor_type=ActorType.AGENT,
    )
    assert ret.qty == 2
    h = _history(session, order)[-1]
    assert (h.to_status, h.actor_type) == ("return_requested", "agent")


def test_return_qty_above_bought_rejected(session):
    user, order, item = _order(session, qty=1)
    _deliver(session, order, days_ago=2)
    with pytest.raises(ConflictError) as e:
        svc.request_return(session, user.id, order.id, item.id, ReturnReason.OTHER, None, qty=2)
    assert e.value.code == "invalid_qty"
    session.expire_all()
    assert session.get(Order, order.id).status == "delivered"


def test_defaults_unchanged(session):
    """Website calls (no new args) behave as before: full qty, customer actor."""
    user, order, item = _order(session, qty=2)
    _deliver(session, order, days_ago=2)
    ret = svc.request_return(session, user.id, order.id, item.id, ReturnReason.DEFECTIVE, None)
    assert ret.qty == 2
    assert _history(session, order)[-1].actor_type == "customer"


# ---- API exposes the item id and delivered_at ----
def test_order_api_has_item_id_and_delivered_at(session):
    user, order, item = _order(session)
    _deliver(session, order, days_ago=1)
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    token = create_access_token(user.id, user.role)
    body = client.get(f"/orders/{order.id}", headers={"Authorization": f"Bearer {token}"}).json()
    assert body["items"][0]["id"] == item.id
    assert body["delivered_at"] is not None
