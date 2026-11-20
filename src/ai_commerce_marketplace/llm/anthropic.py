"""Adapter for Anthropic Claude (Messages API)."""

from collections.abc import Sequence
from typing import Any

import httpx

from ai_commerce_marketplace.llm.base import DEFAULT_TIMEOUT_S, HTTPProvider
from ai_commerce_marketplace.llm.errors import BadResponseError
from ai_commerce_marketplace.llm.types import (
    FinishReason,
    LLMResponse,
    Message,
    ToolCall,
    ToolSpec,
    Usage,
)

BASE_URL = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"
_FINISH: dict[str, FinishReason] = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
    "max_tokens": "length",
}


def _messages(messages: Sequence[Message]) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    out: list[dict[str, Any]] = []

    def add(role: str, blocks: list[dict[str, Any]]) -> None:
        if out and out[-1]["role"] == role:  # parallel tool results go in one user turn
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for m in messages:
        if m.role == "system":
            system.append(m.content)
        elif m.role == "user":
            add("user", [{"type": "text", "text": m.content}])
        elif m.role == "assistant":
            blocks: list[dict[str, Any]] = (
                [{"type": "text", "text": m.content}] if m.content else []
            )
            blocks += [
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in m.tool_calls
            ]
            add("assistant", blocks or [{"type": "text", "text": "..."}])
        else:
            add(
                "user",
                [{"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}],
            )
    return "\n\n".join(system), out


class AnthropicClient(HTTPProvider):
    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        http: httpx.Client | None = None,
    ):
        super().__init__(
            api_key=api_key, model=model, base_url=base_url, timeout=timeout, http=http
        )

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        system, msgs = _messages(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": msgs,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
        data = self._post(
            f"{self.base_url}/messages",
            {"x-api-key": self.api_key, "anthropic-version": API_VERSION},
            payload,
        )
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> LLMResponse:
        blocks = data.get("content")
        if not isinstance(blocks, list):
            raise BadResponseError("anthropic response has no content", provider=self.name)
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = tuple(
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input") or {})
            for b in blocks
            if b.get("type") == "tool_use"
        )
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            tool_calls=calls,
            finish_reason="tool_calls"
            if calls
            else _FINISH.get(str(data.get("stop_reason")), "other"),
            usage=Usage(usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
            provider=self.name,
            model=data.get("model") or self.model,
        )
