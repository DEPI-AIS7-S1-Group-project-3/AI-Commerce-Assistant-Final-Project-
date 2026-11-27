import json
from datetime import date

import pytest

from ai_commerce_marketplace.agents.catalog import AGENTS
from ai_commerce_marketplace.agents.common import (
    ToolInputError,
    safe,
)
from ai_commerce_marketplace.agents.common import (
    call_tool as common_call_tool,
)
from ai_commerce_marketplace.agents.runner import APOLOGY, AgentSpec, run_agent
from ai_commerce_marketplace.agents.tool_specs import tool_specs
from ai_commerce_marketplace.llm import AllProvidersFailed, LLMResponse, Message, ToolCall, Usage
from tests.fakes import FakeLLM, call, say


# ---- a tiny agent with two tools ----
class Ctx:
    def __init__(self):
        self.calls = []


def order_get(ctx, order_id: int):
    """Get an order.

    Args:
        order_id: The order number.
    """
    ctx.calls.append(("order_get", order_id))

    def run():
        if order_id == 404:
            raise ToolInputError("order_not_found", "No such order")
        return {"order_id": order_id, "status": "confirmed", "total_egp": "2359.00"}

    return safe(run)


def ping(ctx):
    """Do nothing."""
    ctx.calls.append(("ping",))
    return {"ok": True}


REGISTRY = {
    "order_get": {"fn": order_get, "description": "One order", "params": ["order_id"]},
    "ping": {"fn": ping, "description": "Ping", "params": []},
}
AGENT = AgentSpec(
    "demo",
    REGISTRY,
    lambda ctx, name, args: common_call_tool(REGISTRY, ctx, name, args),
    lambda today: f"SYSTEM today={today}",
)


def run(llm, message="طلبي فين؟", **kw):
    return run_agent(llm, AGENT, Ctx(), message, **kw)


# ---- the happy paths ----
def test_plain_answer_needs_one_call_and_no_tools():
    llm = FakeLLM(say("أهلاً بيك"))
    r = run(llm)
    assert (r.reply, r.finish, r.rounds, r.trace) == ("أهلاً بيك", "answered", 1, ())
    assert r.provider == "gemini"


def test_prompt_history_and_tools_reach_the_model():
    llm = FakeLLM(say("تمام"))
    history = [Message("user", "سلام"), Message("assistant", "أهلاً")]
    run(llm, "ازيك", history=history, today=date(2026, 11, 23))
    messages, tools = llm.sent[0]
    assert messages[0] == Message("system", "SYSTEM today=2026-11-23")
    assert messages[1:3] == history and messages[3] == Message("user", "ازيك")
    assert [t.name for t in tools] == [t.name for t in tool_specs(REGISTRY)]


def test_tool_round_trip():
    ctx = Ctx()
    llm = FakeLLM(call("order_get", {"order_id": 10002}), say("طلبك مؤكد وإجماليه 2359"))
    r = run_agent(llm, AGENT, ctx, "طلب 10002 فين؟")
    assert ctx.calls == [("order_get", 10002)]
    assert r.finish == "answered" and r.rounds == 2 and r.reply == "طلبك مؤكد وإجماليه 2359"
    # the second call sees the assistant tool call and the tool result, in that order
    second = llm.sent[1][0]
    assert second[-2].role == "assistant" and second[-2].tool_calls[0].name == "order_get"
    assert second[-1].role == "tool" and second[-1].tool_call_id == "c1"
    assert json.loads(second[-1].content)["total_egp"] == "2359.00"
    # trace and results for the router
    (t,) = r.trace
    assert (t.tool, t.arguments, t.ok, t.error) == ("order_get", {"order_id": 10002}, True, None)
    assert r.tool_results[0][0] == "order_get" and r.tool_results[0][1]["status"] == "confirmed"
    assert [m.role for m in r.new_messages] == ["assistant", "tool", "assistant"]


def test_null_arguments_are_dropped_before_the_tool_runs():
    seen = []

    def opt(ctx, order_id: int, section_no: int | None = None):
        """Optional arg.

        Args:
            order_id: The order number.
            section_no: Optional section.
        """
        seen.append(section_no)
        return {"ok": True}

    reg = {"opt": {"fn": opt, "description": "d", "params": ["order_id", "section_no"]}}
    agent = AgentSpec(
        "demo", reg, lambda ctx, n, a: common_call_tool(reg, ctx, n, a), lambda today: "S"
    )
    llm = FakeLLM(call("opt", {"order_id": 1, "section_no": None}), say("تمام"))
    r = run_agent(llm, agent, Ctx(), "x")
    assert seen == [None] and r.trace[0].ok  # null did not reach the tool as a bad value


def test_parallel_tool_calls_all_run_and_all_answer():
    calls = (ToolCall("a", "order_get", {"order_id": 1}), ToolCall("b", "ping", {}))
    first = LLMResponse("", calls, "tool_calls", Usage(), "gemini", "m")
    llm = FakeLLM(first, say("خلصت"))
    ctx = Ctx()
    r = run_agent(llm, AGENT, ctx, "x")
    assert ctx.calls == [("order_get", 1), ("ping",)]
    tool_msgs = [m for m in llm.sent[1][0] if m.role == "tool"]
    assert [m.tool_call_id for m in tool_msgs] == ["a", "b"]
    assert r.finish == "answered"


def test_a_tool_error_is_data_for_the_model_not_a_failure():
    llm = FakeLLM(call("order_get", {"order_id": 404}), say("مش لاقي الطلب ده"))
    r = run(llm)
    assert r.finish == "answered" and r.trace[0].ok is False
    assert r.trace[0].error == "order_not_found"
    assert json.loads(llm.sent[1][0][-1].content)["error"] == "order_not_found"


def test_usage_and_failed_providers_add_up():
    a = LLMResponse(
        "",
        (ToolCall("c", "ping", {}),),
        "tool_calls",
        Usage(10, 2),
        "groq",
        "m",
        ("gemini: rate_limited",),
    )
    llm = FakeLLM(a, say("تمام", provider="gemini", failed_providers=("gemini: rate_limited",)))
    r = run(llm)
    assert (r.usage.input_tokens, r.usage.output_tokens) == (20, 7)
    assert r.failed_providers == ("gemini: rate_limited",)  # reported once


# ---- the safety rails ----
def test_rounds_are_capped():
    llm = FakeLLM(*[call("ping", {}, id=f"c{i}") for i in range(10)])
    r = run(llm, max_rounds=3)
    assert (r.finish, r.rounds, r.reply) == ("max_rounds", 3, APOLOGY)
    assert len(llm.sent) == 3
    assert r.new_messages[-1] == Message("assistant", APOLOGY)  # history ends with a reply


def test_a_wrong_call_gets_one_chance_to_correct():
    llm = FakeLLM(
        call("order_get", {"customer_id": 5, "order_id": 1}),  # forbidden argument
        call("order_get", {"order_id": 1}),
        say("تمام"),
    )
    r = run(llm)
    assert r.finish == "answered"
    assert [t.error for t in r.trace] == ["forbidden_argument", None]
    assert json.loads(llm.sent[1][0][-1].content)["error"] == "forbidden_argument"


def test_a_second_wrong_call_ends_the_run():
    llm = FakeLLM(call("nope", {}), call("order_get", {"order_id": "x", "extra": 1}), say("never"))
    r = run(llm)
    assert (r.finish, r.reply) == ("bad_calls", APOLOGY)
    assert len(llm.sent) == 2


def test_the_model_cannot_use_another_agents_tool():
    llm = FakeLLM(call("cancel_order", {"order_id": 1}), call("ping", {}), say("ok"))
    ctx = Ctx()
    r = run_agent(llm, AGENT, ctx, "الغي طلبي")
    assert r.trace[0].error == "unknown_tool" and ("cancel_order",) not in ctx.calls


def test_empty_answer_is_replaced_by_an_apology():
    r = run(FakeLLM(say("   ")))
    assert (r.finish, r.reply) == ("empty", APOLOGY)


def test_llm_errors_reach_the_caller():
    with pytest.raises(AllProvidersFailed):
        run(FakeLLM(AllProvidersFailed("all down")))


# ---- the real agents ----
@pytest.mark.parametrize("name", list(AGENTS))
def test_every_real_agent_builds_its_prompt_and_schemas(name):
    agent = AGENTS[name]
    assert agent.name == name
    assert len(agent.build_system_prompt(date(2026, 11, 23))) > 200
    assert tool_specs(agent.registry)
