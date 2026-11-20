"""Adapter for every OpenAI-compatible API: Groq, xAI (Grok), OpenRouter, OpenAI itself."""

import json
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

_FINISH: dict[str, FinishReason] = {"stop": "stop", "tool_calls": "tool_calls", "length": "length"}


def _message(m: Message) -> dict[str, Any]:
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    if m.role == "assistant" and m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content or None,
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                }
                for c in m.tool_calls
            ],
        }
    return {"role": m.role, "content": m.content}


class OpenAICompatClient(HTTPProvider):
    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT_S,
        http: httpx.Client | None = None,
        max_tokens_field: str = "max_tokens",  # OpenAI reasoning models want max_completion_tokens
    ):
        super().__init__(
            api_key=api_key, model=model, base_url=base_url, timeout=timeout, http=http
        )
        self.name = name
        self.max_tokens_field = max_tokens_field

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message(m) for m in messages],
            "temperature": temperature,
            self.max_tokens_field: max_tokens,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
            payload["tool_choice"] = "auto"
        data = self._post(
            f"{self.base_url}/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            payload,
        )
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> LLMResponse:
        try:
            choice = data["choices"][0]
            msg = choice["message"]
            calls = tuple(
                ToolCall(
                    id=c["id"],
                    name=c["function"]["name"],
                    arguments=_arguments(c["function"].get("arguments")),
                )
                for c in (msg.get("tool_calls") or [])
            )
        except (KeyError, IndexError, TypeError) as e:
            raise BadResponseError(
                f"{self.name} response has no usable message", provider=self.name
            ) from e
        usage = data.get("usage") or {}
        return LLMResponse(
            text=msg.get("content") or "",
            tool_calls=calls,
            finish_reason="tool_calls"
            if calls
            else _FINISH.get(str(choice.get("finish_reason")), "other"),
            usage=Usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
            provider=self.name,
            model=data.get("model") or self.model,
        )


def _arguments(raw: Any) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError as e:
        raise BadResponseError("tool call arguments are not valid JSON") from e
    if not isinstance(value, dict):
        raise BadResponseError("tool call arguments must be a JSON object")
    return value
