import json
from datetime import UTC, datetime, timedelta

import pytest

from ai_commerce_marketplace.agents.support.tools import REGISTRY, ToolContext, call_tool
from tests import factories as f

NOW = datetime.now(UTC)

RETURNS_BODY = """## 1. مهلة الإرجاع
ترجع المنتج خلال 14 يوم من التسليم.

## 2. منتجات غير قابلة للإرجاع
السماعات الداخلية لا ترجع لأسباب صحية.
"""


def ctx(session, user=None):
    return ToolContext(session=session, customer_id=user.id if user else None)


def make_customer_order(session, user, *, status="pending", delivered_days_ago=None, **product):
    delivered = NOW - timedelta(days=delivered_days_ago) if delivered_days_ago else None
    created = (delivered or NOW) - timedelta(days=3)
    order = f.make_order(
        session,
        customer_id=user.id,
        status=status,
        delivered_at=delivered,
        created_at=created,
        expected_delivery_at=created + timedelta(days=5),
    )
    item = f.make_order_item(session, order=order, product=f.make_product(session, **product))
    return order, item


# ---- the registry ----
def test_registry_has_the_seven_support_tools():
    assert sorted(REGISTRY) == [
        "order_eligibility",
        "order_get",
        "order_list",
        "policy_get",
        "policy_search",
        "return_status",
        "warranty_status",
    ]


def test_no_tool_takes_identity_arguments():
    for name, spec in REGISTRY.items():
        assert not {"customer_id", "user_id", "session", "ctx"} & set(spec["params"]), name


def test_every_tool_result_is_json_serializable(session):
    user = f.make_user(session)
    order, _ = make_customer_order(session, user, status="delivered", delivered_days_ago=3)
    f.make_policy(session, body_md=RETURNS_BODY)
    calls = {
        "policy_search": {"query": "مهلة الإرجاع"},
        "policy_get": {"slug": "returns"},
        "order_list": {},
        "order_get": {"order_id": order.id},
        "order_eligibility": {"order_id": order.id},
        "warranty_status": {"order_id": order.id},
        "return_status": {"order_id": order.id},
    }
    assert set(calls) == set(REGISTRY)
    for name, args in calls.items():
        result = call_tool(ctx(session, user), name, args)
        assert result["ok"] is True, (name, result)
        json.dumps(result)


# ---- safety ----
@pytest.mark.parametrize("forbidden", ["customer_id", "user_id", "seller_id"])
def test_model_cannot_pass_identity(session, forbidden):
    user = f.make_user(session)
    r = call_tool(ctx(session, user), "order_list", {forbidden: 1})
    assert r["ok"] is False and r["error"] == "forbidden_argument"


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("order_list", {}),
        ("order_get", {"order_id": 1}),
        ("order_eligibility", {"order_id": 1}),
        ("warranty_status", {"order_id": 1}),
        ("return_status", {"order_id": 1}),
    ],
)
def test_order_tools_need_a_signed_in_customer(session, tool, args):
    r = call_tool(ctx(session), tool, args)
    assert r["ok"] is False and r["error"] == "login_required"


@pytest.mark.parametrize(
    "tool", ["order_get", "order_eligibility", "warranty_status", "return_status"]
)
def test_another_customers_order_looks_like_a_missing_order(session, tool):
    owner, stranger = f.make_user(session), f.make_user(session)
    order, _ = make_customer_order(session, owner, status="delivered", delivered_days_ago=2)
    mine = call_tool(ctx(session, stranger), tool, {"order_id": order.id})
    missing = call_tool(ctx(session, stranger), tool, {"order_id": order.id + 1000})
    assert mine["ok"] is False and mine["error"] == "order_not_found"
    assert mine == missing  # nothing tells the two cases apart


@pytest.mark.parametrize("bad", [0, -5, True, 1.5, "abc", None])
def test_bad_order_ids_are_rejected(session, bad):
    user = f.make_user(session)
    r = call_tool(ctx(session, user), "order_get", {"order_id": bad})
    assert r["ok"] is False and r["error"] == "invalid_order_id"


def test_order_id_as_digit_string_is_accepted(session):
    user = f.make_user(session)
    order, _ = make_customer_order(session, user)
    assert call_tool(ctx(session, user), "order_get", {"order_id": str(order.id)})["ok"] is True


# ---- orders ----
def test_order_list_is_newest_first_and_limited(session):
    user = f.make_user(session)
    old, _ = make_customer_order(session, user, status="delivered", delivered_days_ago=40)
    new, _ = make_customer_order(session, user)
    r = call_tool(ctx(session, user), "order_list", {"limit": 1})
    assert r["ok"] and r["total_orders"] == 2
    assert [o["order_id"] for o in r["orders"]] == [new.id]
    assert old.id not in [o["order_id"] for o in r["orders"]]


def test_order_list_only_shows_my_orders(session):
    me, other = f.make_user(session), f.make_user(session)
    make_customer_order(session, other)
    r = call_tool(ctx(session, me), "order_list", {})
    assert r["ok"] and r["empty"] is True and r["orders"] == []


def test_order_list_caps_the_limit(session):
    user = f.make_user(session)
    for _ in range(12):
        make_customer_order(session, user)
    r = call_tool(ctx(session, user), "order_list", {"limit": 500})
    assert len(r["orders"]) == 10 and r["total_orders"] == 12


def test_order_get_returns_status_and_expected_delivery(session):
    user = f.make_user(session)
    order, item = make_customer_order(session, user, status="shipped")
    r = call_tool(ctx(session, user), "order_get", {"order_id": order.id})
    assert r["ok"] and r["status"] == "shipped"
    assert r["items"][0]["item_id"] == item.id
    assert r["expected_delivery_at"]  # the agent quotes this date; it never computes one
    assert isinstance(r["timeline"], list)


# ---- eligibility ----
def test_pending_order_can_be_cancelled(session):
    user = f.make_user(session)
    order, _ = make_customer_order(session, user, status="pending")
    r = call_tool(ctx(session, user), "order_eligibility", {"order_id": order.id})
    assert r["can_cancel"] is True and r["cancel_block"] is None
    assert r["items"][0]["can_return"] is False  # not delivered yet


def test_shipped_order_cannot_be_cancelled(session):
    user = f.make_user(session)
    order, _ = make_customer_order(session, user, status="shipped")
    r = call_tool(ctx(session, user), "order_eligibility", {"order_id": order.id})
    assert r["can_cancel"] is False and r["cancel_block"] == "already_shipped"


def test_recent_delivery_can_be_returned(session):
    user = f.make_user(session)
    order, _ = make_customer_order(session, user, status="delivered", delivered_days_ago=3)
    r = call_tool(ctx(session, user), "order_eligibility", {"order_id": order.id})
    assert r["items"][0]["can_return"] is True and r["items"][0]["return_block"] is None


def test_return_window_expired(session):
    user = f.make_user(session)
    order, _ = make_customer_order(session, user, status="delivered", delivered_days_ago=31)
    r = call_tool(ctx(session, user), "order_eligibility", {"order_id": order.id})
    assert r["items"][0]["can_return"] is False
    assert r["items"][0]["return_block"] == "window_expired"


def test_non_returnable_product(session):
    user = f.make_user(session)
    order, _ = make_customer_order(
        session, user, status="delivered", delivered_days_ago=2, is_returnable=False
    )
    (item,) = call_tool(ctx(session, user), "order_eligibility", {"order_id": order.id})["items"]
    assert item["is_returnable"] is False and item["can_return"] is False


# ---- warranty and returns ----
def test_warranty_status_tool(session):
    user = f.make_user(session)
    order, _ = make_customer_order(
        session, user, status="delivered", delivered_days_ago=10, warranty_months=12
    )
    (item,) = call_tool(ctx(session, user), "warranty_status", {"order_id": order.id})["items"]
    assert item["state"] == "active" and item["warranty_months"] == 12
    assert item["ends_at"] and item["days_left"] > 300


def test_return_status_tool(session):
    user = f.make_user(session)
    order, item = make_customer_order(session, user, status="delivered", delivered_days_ago=2)
    empty = call_tool(ctx(session, user), "return_status", {"order_id": order.id})
    assert empty["ok"] and empty["empty"] is True
    f.make_return(session, item, status="requested")
    r = call_tool(ctx(session, user), "return_status", {"order_id": order.id})
    assert r["empty"] is False and r["returns"][0]["status"] == "requested"


# ---- policies (open to visitors) ----
def test_policy_search_works_for_visitors_and_cites_the_source(session):
    f.make_policy(session, body_md=RETURNS_BODY, version="2026-10-01")
    r = call_tool(ctx(session), "policy_search", {"query": "السماعات الداخلية ترجع؟"})
    assert r["ok"] and r["empty"] is False
    top = r["sections"][0]
    assert (top["policy_slug"], top["section_no"], top["version"]) == ("returns", 2, "2026-10-01")
    assert "السماعات" in top["text"]


def test_policy_search_with_no_match_is_empty_not_an_error(session):
    f.make_policy(session, body_md=RETURNS_BODY)
    r = call_tool(ctx(session), "policy_search", {"query": "مين رئيس الجمهورية"})
    assert r["ok"] is True and r["empty"] is True and r["sections"] == []


@pytest.mark.parametrize("query", ["", "   ", None, 5])
def test_policy_search_rejects_empty_queries(session, query):
    r = call_tool(ctx(session), "policy_search", {"query": query})
    assert r["ok"] is False and r["error"] == "empty_query"


def test_policy_search_ignores_old_policy_versions(session):
    f.make_policy(session, body_md=RETURNS_BODY, is_current=False)
    r = call_tool(ctx(session), "policy_search", {"query": "مهلة الإرجاع"})
    assert r["ok"] and r["empty"] is True


def test_policy_get_whole_policy_and_one_section(session):
    f.make_policy(session, body_md=RETURNS_BODY)
    whole = call_tool(ctx(session), "policy_get", {"slug": "returns"})
    assert [s["section_no"] for s in whole["sections"]] == [1, 2]
    one = call_tool(ctx(session), "policy_get", {"slug": "returns", "section_no": 2})
    assert [s["section_no"] for s in one["sections"]] == [2]


def test_policy_get_errors(session):
    f.make_policy(session, body_md=RETURNS_BODY)
    assert call_tool(ctx(session), "policy_get", {"slug": "nope"})["error"] == "invalid_slug"
    assert (
        call_tool(ctx(session), "policy_get", {"slug": "returns", "section_no": 9})["error"]
        == "section_not_found"
    )
    assert (
        call_tool(ctx(session), "policy_get", {"slug": "shipping"})["error"] == "policy_not_found"
    )
