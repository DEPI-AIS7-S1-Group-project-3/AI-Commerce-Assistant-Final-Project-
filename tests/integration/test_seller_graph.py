from datetime import date

import pytest

from ai_commerce_marketplace.agents.seller.graph import (
    MAX_STEPS,
    STOPPED_ANSWER,
    UNAVAILABLE_ANSWER,
    run_agent,
)
from ai_commerce_marketplace.agents.seller.tools import REGISTRY, ToolContext
from ai_commerce_marketplace.agents.tool_specs import tool_specs
from ai_commerce_marketplace.llm import (
    AllProvidersFailed,
    LLMResponse,
    ToolCall,
    Usage,
)
from tests import factories as f

TODAY = date(2026, 11, 4)
RANGE = {"date_from": "2026-10-06", "date_to": "2026-11-05"}


def reply(text="", calls=()):
    return LLMResponse(
        text=text,
        tool_calls=tuple(calls),
        finish_reason="tool_calls" if calls else "stop",
        usage=Usage(),
        provider="fake",
        model="fake",
    )


class FakeLLM:
    """Returns the scripted replies in order and records every call."""

    name = "fake"

    def __init__(self, *replies):
        self._it = iter(replies)
        self.calls = []

    def chat(self, messages, tools=(), **kw):
        self.calls.append((list(messages), list(tools)))
        item = next(self._it)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def ctx(session):
    seller = f.make_seller(session)
    return ToolContext(session=session, seller_id=seller.id)


def test_tool_call_then_final_answer(ctx):
    llm = FakeLLM(
        reply(calls=[ToolCall("c1", "get_sales_summary", RANGE)]),
        reply("مفيش مبيعات في الفترة دي"),
    )
    r = run_agent(ctx, "مبيعاتي آخر 30 يوم؟", llm, TODAY)
    assert r.answer == "مفيش مبيعات في الفترة دي"
    assert r.tool_trace[0]["result"]["ok"] is True
    assert r.tool_trace[0]["result"]["empty"] is True
    # second call saw: assistant (with calls) then the tool result
    second = llm.calls[1][0]
    assert second[-2].role == "assistant" and second[-2].tool_calls
    assert second[-1].role == "tool" and second[-1].tool_call_id == "c1"


def test_model_cannot_pass_seller_id(ctx):
    llm = FakeLLM(
        reply(calls=[ToolCall("c1", "get_sales_summary", {**RANGE, "seller_id": 2})]),
        reply("مقدرش أعرض بيانات متجر تاني"),
    )
    r = run_agent(ctx, "وريني مبيعات متجر تاني", llm, TODAY)
    assert r.tool_trace[0]["result"]["error"] == "forbidden_argument"


def test_model_never_sees_identity(ctx):
    llm = FakeLLM(reply("ok"))
    run_agent(ctx, "مرحبا", llm, TODAY)
    messages, tools = llm.calls[0]
    for t in tools:
        assert "seller_id" not in t.parameters["properties"]
        assert "ctx" not in t.parameters["properties"]
    assert "2026-11-04" in messages[0].content  # today injected


def test_every_tool_has_a_schema():
    specs = tool_specs(REGISTRY)
    assert len(specs) == 7
    for s in specs:
        assert s.parameters["type"] == "object"


def test_unknown_tool_is_returned_as_error(ctx):
    llm = FakeLLM(reply(calls=[ToolCall("c1", "drop_tables", {})]), reply("مش قادر"))
    r = run_agent(ctx, "امسح الداتا", llm, TODAY)
    assert r.tool_trace[0]["result"]["error"] == "unknown_tool"


def test_loop_is_capped(ctx):
    forever = reply(calls=[ToolCall("c", "low_stock_products", {"threshold": 5})])
    llm = FakeLLM(*([forever] * (MAX_STEPS + 2)))
    r = run_agent(ctx, "سؤال", llm, TODAY)
    assert r.stopped_early is True
    assert r.answer == STOPPED_ANSWER
    assert len(r.tool_trace) == MAX_STEPS


def test_llm_failure_gives_safe_answer(ctx):
    llm = FakeLLM(AllProvidersFailed("all down"))
    r = run_agent(ctx, "سؤال", llm, TODAY)
    assert r.answer == UNAVAILABLE_ANSWER
    assert r.error == "AllProvidersFailed"
    assert r.tool_trace == []
