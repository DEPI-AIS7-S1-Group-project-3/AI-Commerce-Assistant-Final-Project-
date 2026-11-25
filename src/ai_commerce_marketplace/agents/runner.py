"""The tool-calling loop that runs one agent for one user message.

    prompt + history + message -> LLM -> tool calls -> tool results -> LLM -> ... -> answer

The loop is the same for every agent. What differs is an ``AgentSpec``: the agent's tools, its
``call_tool`` and its system prompt. The loop never decides who the user is (that is in the
``ToolContext`` the router built from the token) and never runs a tool the agent does not have.

Safety rails:

- at most ``max_rounds`` LLM calls per message (a free-tier quota matters, and so do loops);
- a tool call the model got wrong (unknown tool, forbidden or bad arguments) is returned to the
  model once so it can correct itself; a second one ends the run;
- an empty answer, too many rounds or a second bad call end with a short Arabic apology, never
  with made-up content.

LLM errors (``AllProvidersFailed`` and friends) are not caught here: the router turns them into
a 503.
"""

import json
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from ai_commerce_marketplace.agents.common import ToolRegistry
from ai_commerce_marketplace.agents.tool_specs import tool_specs
from ai_commerce_marketplace.llm import LLMClient, LLMResponse, Message, ToolCall, Usage

MAX_ROUNDS = 5
APOLOGY = "حصلت مشكلة مؤقتة وأنا بجاوب. ممكن تعيد سؤالك؟"
# Errors that mean the model built the call wrongly (not that the data is missing).
CALL_ERRORS = {"unknown_tool", "forbidden_argument", "bad_arguments"}

Finish = Literal["answered", "max_rounds", "bad_calls", "empty"]


@dataclass(frozen=True)
class AgentSpec:
    name: str
    registry: ToolRegistry
    call_tool: Callable[[Any, str, dict[str, Any]], dict[str, Any]]
    build_system_prompt: Callable[[date | None], str]


@dataclass(frozen=True)
class ToolTrace:
    tool: str
    arguments: dict[str, Any]
    ok: bool
    error: str | None
    ms: int


@dataclass(frozen=True)
class AgentResult:
    reply: str
    finish: Finish
    rounds: int
    trace: tuple[ToolTrace, ...]
    # Full results, for the router (for example to pick product ids). Not for the response.
    tool_results: tuple[tuple[str, dict[str, Any]], ...]
    # Assistant and tool messages added after the user message, for conversation storage.
    new_messages: tuple[Message, ...]
    usage: Usage
    provider: str | None
    model: str | None
    failed_providers: tuple[str, ...] = field(default=())


def _tool_message(call: ToolCall, result: dict[str, Any]) -> Message:
    content = json.dumps(result, ensure_ascii=False, default=str)
    return Message("tool", content, tool_call_id=call.id, name=call.name)


def run_agent(
    llm: LLMClient,
    agent: AgentSpec,
    ctx: Any,
    message: str,
    history: Sequence[Message] = (),
    *,
    today: date | None = None,
    max_rounds: int = MAX_ROUNDS,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> AgentResult:
    specs = tool_specs(agent.registry)
    messages: list[Message] = [
        Message("system", agent.build_system_prompt(today)),
        *history,
        Message("user", message),
    ]
    start = len(messages)
    trace: list[ToolTrace] = []
    results: list[tuple[str, dict[str, Any]]] = []
    failed: list[str] = []
    tokens_in = tokens_out = 0
    bad_calls = 0
    last: LLMResponse | None = None

    def finish(reply: str, how: Finish, rounds: int) -> AgentResult:
        if how != "answered":  # keep the stored history well formed: every turn ends with a reply
            messages.append(Message("assistant", reply))
        return AgentResult(
            reply=reply,
            finish=how,
            rounds=rounds,
            trace=tuple(trace),
            tool_results=tuple(results),
            new_messages=tuple(messages[start:]),
            usage=Usage(tokens_in, tokens_out),
            provider=last.provider if last else None,
            model=last.model if last else None,
            failed_providers=tuple(dict.fromkeys(failed)),
        )

    for rounds in range(1, max_rounds + 1):
        last = llm.chat(messages, specs, temperature=temperature, max_tokens=max_tokens)
        tokens_in += last.usage.input_tokens
        tokens_out += last.usage.output_tokens
        failed.extend(last.failed_providers)

        if not last.tool_calls:
            text = last.text.strip()
            if not text:
                return finish(APOLOGY, "empty", rounds)
            messages.append(Message("assistant", text))
            return finish(text, "answered", rounds)

        messages.append(Message("assistant", last.text, last.tool_calls))
        for call in last.tool_calls:
            began = time.monotonic()
            result = agent.call_tool(ctx, call.name, call.arguments)
            trace.append(
                ToolTrace(
                    tool=call.name,
                    arguments=call.arguments,
                    ok=bool(result.get("ok")),
                    error=result.get("error"),
                    ms=round((time.monotonic() - began) * 1000),
                )
            )
            results.append((call.name, result))
            messages.append(_tool_message(call, result))
            if result.get("error") in CALL_ERRORS:
                bad_calls += 1
        if bad_calls > 1:
            return finish(APOLOGY, "bad_calls", rounds)

    return finish(APOLOGY, "max_rounds", max_rounds)
