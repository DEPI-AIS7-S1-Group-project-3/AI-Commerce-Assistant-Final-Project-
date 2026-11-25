"""Seller Agent loop on the shared LLM layer.

llm.chat(messages, tools) -> tool calls -> call_tool -> llm.chat ... -> final text.
Every tool call goes through call_tool, so identity rules and isolation always apply.
The model never sees seller_id or ctx.
"""

import json
from dataclasses import dataclass
from datetime import date

from ai_commerce_marketplace.agents.seller.prompts import build_system_prompt
from ai_commerce_marketplace.agents.seller.tools import REGISTRY, ToolContext, call_tool
from ai_commerce_marketplace.agents.tool_specs import tool_specs as build_tool_specs
from ai_commerce_marketplace.llm import LLMClient, LLMError, Message, ToolCall

MAX_STEPS = 5

UNAVAILABLE_ANSWER = "المساعد مش متاح دلوقتي. جرّب تاني بعد شوية."
STOPPED_ANSWER = "مقدرتش أوصل لإجابة كاملة. جرّب تسأل بشكل أبسط أو تحدد الفترة."


@dataclass
class AgentResult:
    answer: str
    tool_trace: list[dict]
    stopped_early: bool = False
    error: str | None = None  # LLMError class name when the model could not be reached


def _run_tool(ctx: ToolContext, call: ToolCall, trace: list[dict]) -> Message:
    result = call_tool(ctx, call.name, call.arguments)
    trace.append({"tool": call.name, "args": call.arguments, "result": result})
    return Message(
        "tool",
        json.dumps(result, ensure_ascii=False),
        tool_call_id=call.id,
        name=call.name,
    )


def run_agent(
    ctx: ToolContext,
    user_message: str,
    llm: LLMClient,
    today: date | None = None,
) -> AgentResult:
    messages: list[Message] = [
        Message("system", build_system_prompt(today)),
        Message("user", user_message),
    ]
    tools = build_tool_specs(REGISTRY)
    trace: list[dict] = []

    for _ in range(MAX_STEPS):
        try:
            reply = llm.chat(messages, tools)
        except LLMError as e:
            return AgentResult(
                answer=UNAVAILABLE_ANSWER,
                tool_trace=trace,
                error=type(e).__name__,
            )
        if not reply.tool_calls:
            return AgentResult(answer=reply.text or "", tool_trace=trace)
        # the assistant message that carried the calls must come before the tool results
        messages.append(Message("assistant", reply.text or "", tool_calls=reply.tool_calls))
        for call in reply.tool_calls:
            messages.append(_run_tool(ctx, call, trace))

    return AgentResult(answer=STOPPED_ANSWER, tool_trace=trace, stopped_early=True)
