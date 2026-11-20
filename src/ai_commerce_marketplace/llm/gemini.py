"""Adapter for Google Gemini (generateContent REST API)."""

import json
import uuid
from collections.abc import Sequence
from typing import Any

import httpx

from ai_commerce_marketplace.llm.base import DEFAULT_TIMEOUT_S, HTTPProvider
from ai_commerce_marketplace.llm.errors import BadResponseError
from ai_commerce_marketplace.llm.types import LLMResponse, Message, ToolCall, ToolSpec, Usage

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
# Gemini 3 wants a thought signature on every function call it is given back. We keep the real
# one in ToolCall.provider_data; this placeholder is only for calls made by another provider.
SKIP_SIGNATURE = "skip_thought_signature_validator"
_UNSUPPORTED_SCHEMA_KEYS = {"additionalProperties", "$schema", "$defs", "title", "default"}


def clean_schema(schema: Any) -> Any:
    """Gemini accepts a subset of JSON schema, so drop the keys it rejects."""
    if isinstance(schema, dict):
        return {k: clean_schema(v) for k, v in schema.items() if k not in _UNSUPPORTED_SCHEMA_KEYS}
    if isinstance(schema, list):
        return [clean_schema(v) for v in schema]
    return schema


def _tool_result(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except ValueError:
        return {"result": content}
    return value if isinstance(value, dict) else {"result": value}


def _contents(messages: Sequence[Message]) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    contents: list[dict[str, Any]] = []

    def add(role: str, parts: list[dict[str, Any]]) -> None:
        if contents and contents[-1]["role"] == role:  # same-role turns must be one turn
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": parts})

    for m in messages:
        if m.role == "system":
            system.append(m.content)
        elif m.role == "user":
            add("user", [{"text": m.content}])
        elif m.role == "assistant":
            parts: list[dict[str, Any]] = [{"text": m.content}] if m.content else []
            for c in m.tool_calls:
                parts.append(
                    c.provider_data
                    or {
                        "functionCall": {"name": c.name, "args": c.arguments},
                        "thoughtSignature": SKIP_SIGNATURE,
                    }
                )
            add("model", parts or [{"text": ""}])
        else:  # tool result
            add(
                "user",
                [{"functionResponse": {"name": m.name, "response": _tool_result(m.content)}}],
            )
    return "\n\n".join(system), contents


class GeminiClient(HTTPProvider):
    name = "gemini"

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
        system, contents = _contents(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": clean_schema(t.parameters),
                        }
                        for t in tools
                    ]
                }
            ]
        data = self._post(
            f"{self.base_url}/models/{self.model}:generateContent",
            {"x-goog-api-key": self.api_key},  # header, so the key never lands in a URL or log
            payload,
        )
        return self._parse(data)

    def _parse(self, data: dict[str, Any]) -> LLMResponse:
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
            raise BadResponseError(f"gemini returned no answer ({reason})", provider=self.name)
        cand = candidates[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))
        calls = tuple(
            ToolCall(
                id=f"call_{uuid.uuid4().hex[:12]}",  # Gemini does not give call ids
                name=p["functionCall"]["name"],
                arguments=p["functionCall"].get("args") or {},
                provider_data=p,
            )
            for p in parts
            if "functionCall" in p
        )
        finish = cand.get("finishReason")
        usage = data.get("usageMetadata") or {}
        return LLMResponse(
            text=text,
            tool_calls=calls,
            finish_reason="tool_calls" if calls else "length" if finish == "MAX_TOKENS" else "stop",
            usage=Usage(usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)),
            provider=self.name,
            model=data.get("modelVersion") or self.model,
        )
