"""Provider-neutral types shared by every LLM adapter.

The agents and the router only ever see these types. Each adapter translates them to the
wire format of its own provider, so changing the model never touches agent code.
"""

from dataclasses import dataclass
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]
FinishReason = Literal["stop", "tool_calls", "length", "other"]


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call. ``parameters`` is a JSON-schema object."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    # Opaque data the same provider needs back on the next turn (for example Gemini's
    # thought signature). Other providers ignore it.
    provider_data: dict[str, Any] | None = None


@dataclass(frozen=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()  # only on assistant messages
    tool_call_id: str | None = None  # only on tool messages
    name: str | None = None  # tool name, only on tool messages


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tool_calls: tuple[ToolCall, ...]
    finish_reason: FinishReason
    usage: Usage
    provider: str
    model: str
    # Providers that failed before this one answered, e.g. ("gemini: rate_limited",).
    failed_providers: tuple[str, ...] = ()
