"""Seller Agent entry point: a thin wrapper over the shared agent runner.

The loop itself (rounds cap, bad-call correction, tracing, history) lives in
``agents/runner.py`` and is the same for every agent. This module keeps the seller-specific
signature ``run_agent(ctx, message, llm)`` and its simple result shape.
The model never sees seller_id or ctx.
"""

from dataclasses import dataclass
from datetime import date

from ai_commerce_marketplace.agents import runner
from ai_commerce_marketplace.agents.seller import prompts, tools
from ai_commerce_marketplace.agents.tool_specs import tool_specs as build_tool_specs
from ai_commerce_marketplace.llm import LLMClient, LLMError, ToolSpec

MAX_STEPS = runner.MAX_ROUNDS

UNAVAILABLE_ANSWER = "المساعد مش متاح دلوقتي. جرّب تاني بعد شوية."
STOPPED_ANSWER = "مقدرتش أوصل لإجابة كاملة. جرّب تسأل بشكل أبسط أو تحدد الفترة."

SPEC = runner.AgentSpec("seller", tools.REGISTRY, tools.call_tool, prompts.build_system_prompt)


@dataclass
class AgentResult:
    answer: str
    tool_trace: list[dict]
    stopped_early: bool = False
    error: str | None = None  # LLMError class name when the model could not be reached


def tool_specs() -> list[ToolSpec]:
    """What the model may see: name, description, JSON schema. Never ctx or seller_id."""
    return build_tool_specs(tools.REGISTRY)


def run_agent(
    ctx: tools.ToolContext,
    user_message: str,
    llm: LLMClient,
    today: date | None = None,
) -> AgentResult:
    try:
        r = runner.run_agent(llm, SPEC, ctx, user_message, today=today, max_rounds=MAX_STEPS)
    except LLMError as e:
        return AgentResult(answer=UNAVAILABLE_ANSWER, tool_trace=[], error=type(e).__name__)
    trace = [
        {"tool": t.tool, "args": t.arguments, "result": res}
        for t, (_, res) in zip(r.trace, r.tool_results, strict=True)
    ]
    if r.finish == "answered":
        return AgentResult(answer=r.reply, tool_trace=trace)
    return AgentResult(answer=STOPPED_ANSWER, tool_trace=trace, stopped_early=True)
