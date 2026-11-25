"""The runner with the real Support agent and the real tools on the test database.

The LLM is scripted, so this checks the plumbing (real tool results go back to the model, the
identity comes from the context, a visitor is stopped by the tool), not the model's wording.
"""

import json
from datetime import UTC, datetime, timedelta

from ai_commerce_marketplace.agents.catalog import AGENTS
from ai_commerce_marketplace.agents.runner import run_agent
from ai_commerce_marketplace.agents.support.tools import ToolContext
from tests import factories as f
from tests.fakes import FakeLLM, call, say

NOW = datetime.now(UTC)


def delivered_order(session, user, days_ago=3):
    delivered = NOW - timedelta(days=days_ago)
    order = f.make_order(
        session,
        customer_id=user.id,
        status="delivered",
        delivered_at=delivered,
        created_at=delivered - timedelta(days=3),
    )
    f.make_order_item(session, order=order, product=f.make_product(session))
    return order


def test_real_tool_result_reaches_the_model(session):
    user = f.make_user(session)
    order = delivered_order(session, user)
    llm = FakeLLM(call("order_eligibility", {"order_id": order.id}), say("أيوه ينفع ترجعه"))
    ctx = ToolContext(session=session, customer_id=user.id)
    r = run_agent(llm, AGENTS["support"], ctx, f"ينفع ارجع {order.id}؟")
    sent = json.loads(llm.sent[1][0][-1].content)
    assert sent["ok"] is True and sent["items"][0]["can_return"] is True
    assert r.finish == "answered" and r.trace[0].tool == "order_eligibility"


def test_another_customers_order_looks_missing(session):
    owner, stranger = f.make_user(session), f.make_user(session)
    order = delivered_order(session, owner)
    llm = FakeLLM(call("order_get", {"order_id": order.id}), say("مش لاقي الطلب"))
    ctx = ToolContext(session=session, customer_id=stranger.id)
    r = run_agent(llm, AGENTS["support"], ctx, "طلبي")
    assert json.loads(llm.sent[1][0][-1].content)["error"] == "order_not_found"
    assert r.trace[0].error == "order_not_found"


def test_model_cannot_choose_the_customer(session):
    victim, attacker = f.make_user(session), f.make_user(session)
    order = delivered_order(session, victim)
    llm = FakeLLM(
        call("order_get", {"order_id": order.id, "customer_id": victim.id}),
        say("مش قادر"),
    )
    ctx = ToolContext(session=session, customer_id=attacker.id)
    r = run_agent(llm, AGENTS["support"], ctx, "طلب الغير")
    assert r.trace[0].error == "forbidden_argument"


def test_a_visitor_is_stopped_by_the_tool_not_by_the_prompt(session):
    llm = FakeLLM(call("order_list", {}), say("سجّل دخولك الأول"))
    r = run_agent(llm, AGENTS["support"], ToolContext(session=session), "طلباتي")
    assert r.trace[0].error == "login_required"
