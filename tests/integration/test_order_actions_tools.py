"""Order Actions Agent tools: identity, read tools, eligibility and the confirmation flow."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from ai_commerce_marketplace.agents.order_actions.tools import (
    MESSAGES_AR,
    REGISTRY,
    ToolContext,
    call_tool,
    execute_confirmed,
)
from ai_commerce_marketplace.core.enums import ActorType, OrderStatus
from ai_commerce_marketplace.database.models.order import Order, OrderStatusHistory, Return
from ai_commerce_marketplace.services.order_state import change_status
from tests import factories as f

S = OrderStatus


@pytest.fixture
def customer(session):
    return f.make_user(session)


@pytest.fixture
def ctx(session, customer):
    return ToolContext(session=session, customer_id=customer.id)


def _order(session, customer, qty=2, returnable=True, **kw):
    order = f.make_order(session, customer_id=customer.id, **kw)
    product = f.make_product(session, stock_qty=10, is_returnable=returnable)
    item = f.make_order_item(session, order=order, product=product, qty=qty)
    session.commit()
    return order, item, product


def _move(session, order, *targets):
    for t in targets:
        change_status(session, order, t, actor_type=ActorType.SELLER)
    session.commit()


def _deliver(session, order, days_ago):
    _move(session, order, S.CONFIRMED, S.SHIPPED, S.OUT_FOR_DELIVERY, S.DELIVERED)
    order.created_at = datetime.now(UTC) - timedelta(days=days_ago + 5)
    order.delivered_at = datetime.now(UTC) - timedelta(days=days_ago)
    session.commit()


def _history(session, order):
    return session.scalars(
        select(OrderStatusHistory)
        .where(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.id)
    ).all()


# ---- identity and registry ----
@pytest.mark.parametrize("field", ["customer_id", "user_id", "session", "ctx", "now"])
def test_llm_cannot_pass_identity(ctx, field):
    for name in REGISTRY:
        r = call_tool(ctx, name, {field: 1})
        assert r["ok"] is False
        assert r["error"] == "forbidden_argument"


def test_unknown_tool(ctx):
    r = call_tool(ctx, "delete_everything", {})
    assert (r["ok"], r["error"]) == (False, "unknown_tool")


def test_missing_arguments(ctx):
    r = call_tool(ctx, "get_order", {})
    assert (r["ok"], r["error"]) == (False, "bad_arguments")


def test_every_error_code_has_arabic_message():
    codes = {
        "already_cancelled",
        "already_returned",
        "already_delivered",
        "already_shipped",
        "not_delivered",
        "not_returnable",
        "return_exists",
        "window_expired",
        "invalid_qty",
        "order_not_found",
        "order_item_not_found",
        "invalid_transition",
    }
    assert codes <= set(MESSAGES_AR)


# ---- read tools ----
def test_list_only_own_orders(session, ctx, customer):
    mine, _, _ = _order(session, customer)
    other = f.make_user(session)
    _order(session, other)
    r = call_tool(ctx, "list_my_orders", {})
    assert r["ok"] is True
    assert [o["id"] for o in r["orders"]] == [mine.id]
    assert r["orders"][0]["status_ar"] == "قيد المراجعة"
    assert "seller_id" not in r["orders"][0]
    assert "phone" not in str(r["orders"][0])  # no address details for the model


def test_list_filter_and_empty(session, ctx, customer):
    _order(session, customer)
    assert call_tool(ctx, "list_my_orders", {"status": "pending"})["total"] == 1
    r = call_tool(ctx, "list_my_orders", {"status": "delivered"})
    assert (r["ok"], r["empty"], r["orders"]) == (True, True, [])
    bad = call_tool(ctx, "list_my_orders", {"status": "lost"})
    assert (bad["ok"], bad["error"]) == (False, "invalid_status")


def test_list_limit_capped(session, ctx, customer):
    for _ in range(3):
        _order(session, customer)
    r = call_tool(ctx, "list_my_orders", {"limit": 2})
    assert (len(r["orders"]), r["total"]) == (2, 3)
    assert call_tool(ctx, "list_my_orders", {"limit": 0})["error"] == "invalid_limit"


def test_get_order_with_timeline_and_item_ids(session, ctx, customer):
    order, item, _ = _order(session, customer)
    _move(session, order, S.CONFIRMED)
    r = call_tool(ctx, "get_order", {"order_id": order.id})
    assert r["ok"] is True
    o = r["order"]
    assert o["items"][0]["order_item_id"] == item.id
    assert [t["to_status"] for t in o["timeline"]] == ["confirmed"]
    assert o["timeline"][0]["to_status_ar"] == "اتأكد ومستني الشحن"


def test_other_customers_order_looks_like_missing_order(session, ctx):
    other = f.make_user(session)
    theirs, _, _ = _order(session, other)
    hidden = call_tool(ctx, "get_order", {"order_id": theirs.id})
    missing = call_tool(ctx, "get_order", {"order_id": 999999})
    assert hidden == missing
    assert hidden["error"] == "order_not_found"
    assert hidden["message_ar"] == "مش لاقي طلب بالرقم ده في حسابك."


@pytest.mark.parametrize("bad", [0, -5, "10002", True, None])
def test_bad_order_id(ctx, bad):
    assert call_tool(ctx, "get_order", {"order_id": bad})["error"] == "invalid_order_id"


def test_days_late_for_late_order(session, ctx, customer):
    order, _, _ = _order(
        session, customer, expected_delivery_at=datetime.now(UTC) - timedelta(days=5, hours=1)
    )
    _move(session, order, S.CONFIRMED, S.SHIPPED, S.OUT_FOR_DELIVERY)
    r = call_tool(ctx, "get_order", {"order_id": order.id})
    assert r["order"]["days_late"] == 5


# ---- cancel ----
def test_check_cancel_allowed(session, ctx, customer):
    order, _, _ = _order(session, customer)
    r = call_tool(ctx, "check_cancel_eligibility", {"order_id": order.id})
    assert (r["ok"], r["allowed"], r["reason_code"]) == (True, True, "ok")


def test_check_cancel_after_shipping(session, ctx, customer):
    order, _, _ = _order(session, customer)
    _move(session, order, S.CONFIRMED, S.SHIPPED)
    r = call_tool(ctx, "check_cancel_eligibility", {"order_id": order.id})
    assert (r["allowed"], r["reason_code"]) == (False, "already_shipped")
    assert r["message_ar"] == MESSAGES_AR["already_shipped"]


def test_check_cancel_delivered_suggests_return(session, ctx, customer):
    order, _, _ = _order(session, customer)
    _deliver(session, order, days_ago=3)
    r = call_tool(ctx, "check_cancel_eligibility", {"order_id": order.id})
    assert (r["allowed"], r["reason_code"], r["alternative"]) == (
        False,
        "already_delivered",
        "return",
    )


def test_cancel_tool_only_proposes(session, ctx, customer):
    order, _, product = _order(session, customer, qty=3)
    r = call_tool(ctx, "cancel_order", {"order_id": order.id})
    assert r["ok"] is True
    assert r["needs_confirmation"] is True
    assert r["pending_action"] == {
        "tool": "cancel_order",
        "args": {"order_id": order.id, "reason_code": "customer_request"},
    }
    assert str(order.id) in r["confirm_question_ar"]
    assert "1060.00" in r["confirm_question_ar"]  # total comes from the database
    session.expire_all()
    assert session.get(Order, order.id).status == "pending"
    assert product.stock_qty == 10
    assert _history(session, order) == []


def test_cancel_confirmed_executes(session, ctx, customer):
    order, _, product = _order(session, customer, qty=3)
    pending = call_tool(ctx, "cancel_order", {"order_id": order.id, "reason_code": "late_delivery"})
    r = execute_confirmed(ctx, pending["pending_action"])
    assert (r["ok"], r["done"], r["status"]) == (True, True, "cancelled")
    session.refresh(product)
    assert product.stock_qty == 13
    h = _history(session, order)[-1]
    assert (h.to_status, h.actor_type, h.reason_code) == ("cancelled", "agent", "late_delivery")


def test_cancel_not_allowed_gives_no_pending_action(session, ctx, customer):
    order, _, _ = _order(session, customer)
    _move(session, order, S.CONFIRMED, S.SHIPPED)
    r = call_tool(ctx, "cancel_order", {"order_id": order.id})
    assert (r["ok"], r["allowed"], r["needs_confirmation"]) == (True, False, False)
    assert "pending_action" not in r


def test_status_changed_between_confirm_and_execute(session, ctx, customer):
    order, _, product = _order(session, customer)
    pending = call_tool(ctx, "cancel_order", {"order_id": order.id})["pending_action"]
    _move(session, order, S.CONFIRMED, S.SHIPPED)  # seller shipped meanwhile
    r = execute_confirmed(ctx, pending)
    assert (r["ok"], r["error"]) == (False, "already_shipped")
    session.expire_all()
    assert session.get(Order, order.id).status == "shipped"
    assert product.stock_qty == 10


def test_bad_cancel_reason(session, ctx, customer):
    order, _, _ = _order(session, customer)
    r = call_tool(ctx, "cancel_order", {"order_id": order.id, "reason_code": "seller_out_of_stock"})
    assert (r["ok"], r["error"]) == (False, "invalid_reason")


def test_pending_action_of_other_customer_cannot_run(session, ctx):
    other = f.make_user(session)
    theirs, _, _ = _order(session, other)
    action = {"tool": "cancel_order", "args": {"order_id": theirs.id}}
    r = execute_confirmed(ctx, action)
    assert r["error"] == "order_not_found"
    session.expire_all()
    assert session.get(Order, theirs.id).status == "pending"


@pytest.mark.parametrize(
    "action",
    [
        {"tool": "get_order", "args": {"order_id": 1}},
        {"tool": "drop_db", "args": {}},
        {"tool": "cancel_order"},
        "cancel_order",
        None,
    ],
)
def test_execute_confirmed_only_runs_actions(ctx, action):
    r = execute_confirmed(ctx, action)
    assert (r["ok"], r["error"]) == (False, "not_an_action")


def test_execute_confirmed_rejects_identity(session, ctx, customer):
    order, _, _ = _order(session, customer)
    r = execute_confirmed(
        ctx, {"tool": "cancel_order", "args": {"order_id": order.id, "customer_id": 1}}
    )
    assert r["error"] == "forbidden_argument"


# ---- return ----
def test_check_return_allowed_with_deadline(session, ctx, customer):
    order, item, _ = _order(session, customer)
    _deliver(session, order, days_ago=3)
    r = call_tool(ctx, "check_return_eligibility", {"order_id": order.id, "order_item_id": item.id})
    assert (r["ok"], r["allowed"], r["qty"], r["max_qty"]) == (True, True, 2, 2)
    assert r["days_since_delivery"] == 3
    assert r["return_deadline"]


def test_check_return_window_expired(session, ctx, customer):
    order, item, _ = _order(session, customer)
    _deliver(session, order, days_ago=31)
    r = call_tool(ctx, "check_return_eligibility", {"order_id": order.id, "order_item_id": item.id})
    assert (r["allowed"], r["reason_code"]) == (False, "window_expired")


def test_check_return_not_returnable(session, ctx, customer):
    order, item, _ = _order(session, customer, returnable=False)
    _deliver(session, order, days_ago=1)
    r = call_tool(ctx, "check_return_eligibility", {"order_id": order.id, "order_item_id": item.id})
    assert r["reason_code"] == "not_returnable"


@pytest.mark.parametrize("qty", [3, 0])
def test_check_return_bad_qty(session, ctx, customer, qty):
    order, item, _ = _order(session, customer, qty=2)
    _deliver(session, order, days_ago=1)
    r = call_tool(
        ctx,
        "check_return_eligibility",
        {"order_id": order.id, "order_item_id": item.id, "qty": qty},
    )
    assert r.get("reason_code", r.get("error")) == "invalid_qty"


def test_return_proposal_then_confirm(session, ctx, customer):
    order, item, _ = _order(session, customer, qty=3)
    _deliver(session, order, days_ago=2)
    args = {
        "order_id": order.id,
        "order_item_id": item.id,
        "qty": 1,
        "reason_code": "defective",
        "reason_text": "الشاشة بترعش",
    }
    proposal = call_tool(ctx, "request_return", args)
    assert proposal["needs_confirmation"] is True
    assert session.scalar(select(func.count()).select_from(Return)) == 0

    r = execute_confirmed(ctx, proposal["pending_action"])
    assert (r["ok"], r["done"], r["qty"], r["return_status"]) == (True, True, 1, "requested")
    row = session.get(Return, r["return_id"])
    assert (row.qty, row.reason_code, row.reason_text) == (1, "defective", "الشاشة بترعش")
    h = _history(session, order)[-1]
    assert (h.to_status, h.actor_type) == ("return_requested", "agent")


def test_return_bad_reason(session, ctx, customer):
    order, item, _ = _order(session, customer)
    _deliver(session, order, days_ago=2)
    r = call_tool(
        ctx,
        "request_return",
        {"order_id": order.id, "order_item_id": item.id, "reason_code": "because"},
    )
    assert r["error"] == "invalid_reason"


def test_return_not_allowed_gives_no_pending_action(session, ctx, customer):
    order, item, _ = _order(session, customer)
    _deliver(session, order, days_ago=20)
    r = call_tool(
        ctx,
        "request_return",
        {"order_id": order.id, "order_item_id": item.id, "reason_code": "defective"},
    )
    assert (r["allowed"], r["needs_confirmation"], r["reason_code"]) == (
        False,
        False,
        "window_expired",
    )
    assert "pending_action" not in r


def test_item_from_another_order(session, ctx, customer):
    order, _, _ = _order(session, customer)
    _, other_item, _ = _order(session, customer)
    _deliver(session, order, days_ago=1)
    r = call_tool(
        ctx, "check_return_eligibility", {"order_id": order.id, "order_item_id": other_item.id}
    )
    assert r["error"] == "order_item_not_found"
