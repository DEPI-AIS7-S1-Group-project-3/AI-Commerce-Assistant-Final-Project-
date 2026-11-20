import json

import httpx
import pytest

from ai_commerce_marketplace.llm import (
    AllProvidersFailed,
    AuthenticationError,
    BadResponseError,
    InvalidRequestError,
    Message,
    NotConfiguredError,
    ProviderUnavailable,
    RateLimitError,
    ToolCall,
    ToolSpec,
    build_llm_client,
)
from ai_commerce_marketplace.llm.anthropic import AnthropicClient
from ai_commerce_marketplace.llm.factory import parse_provider_list
from ai_commerce_marketplace.llm.fallback import FallbackClient
from ai_commerce_marketplace.llm.gemini import SKIP_SIGNATURE, GeminiClient, clean_schema
from ai_commerce_marketplace.llm.openai_compat import OpenAICompatClient

TOOL = ToolSpec(
    "order_get",
    "One order",
    {
        "type": "object",
        "properties": {"order_id": {"type": "integer"}},
        "required": ["order_id"],
        "additionalProperties": False,
    },
)
HISTORY = [
    Message("system", "You are the support agent."),
    Message("user", "فين طلبي 10001؟"),
]


def http(handler):
    """An httpx client that never touches the network."""
    return httpx.Client(transport=httpx.MockTransport(handler))


def reply(body, status=200):
    return lambda request: httpx.Response(status, json=body)


# ---- OpenAI-compatible (Groq, Grok, OpenRouter, OpenAI) ----
def openai_client(handler, name="groq"):
    return OpenAICompatClient(
        name=name, api_key="k", model="m", base_url="https://x.test/v1", http=http(handler)
    )


def test_openai_text_reply_and_usage():
    c = openai_client(
        reply(
            {
                "model": "m-1",
                "choices": [{"message": {"content": "أهلاً"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            }
        )
    )
    r = c.chat(HISTORY)
    assert (r.text, r.finish_reason, r.provider, r.model) == ("أهلاً", "stop", "groq", "m-1")
    assert (r.usage.input_tokens, r.usage.output_tokens) == (7, 2)
    assert r.tool_calls == ()


def test_openai_request_shape_and_auth_header():
    seen = {}

    def handler(request):
        seen["url"], seen["auth"] = str(request.url), request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    openai_client(handler).chat(HISTORY, [TOOL], max_tokens=50)
    assert seen["url"] == "https://x.test/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert seen["body"]["max_tokens"] == 50 and seen["body"]["tool_choice"] == "auto"
    assert seen["body"]["tools"][0]["function"]["name"] == "order_get"
    assert seen["body"]["messages"][0] == {
        "role": "system",
        "content": "You are the support agent.",
    }


def test_openai_tool_call_round_trip():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "order_get",
                                        "arguments": '{"order_id": 10001}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    c = openai_client(handler)
    r = c.chat(HISTORY, [TOOL])
    assert r.finish_reason == "tool_calls"
    (call,) = r.tool_calls
    assert (call.id, call.name, call.arguments) == ("c1", "order_get", {"order_id": 10001})

    c.chat(
        [
            *HISTORY,
            Message("assistant", tool_calls=(call,)),
            Message("tool", '{"ok": true}', tool_call_id="c1", name="order_get"),
        ]
    )
    assistant, tool = seen["body"]["messages"][-2:]
    assert assistant["tool_calls"][0]["function"]["arguments"] == '{"order_id": 10001}'
    assert tool == {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'}


def test_openai_rejects_broken_tool_arguments():
    body = {
        "choices": [
            {
                "message": {
                    "tool_calls": [{"id": "c", "function": {"name": "t", "arguments": "{oops"}}]
                }
            }
        ]
    }
    with pytest.raises(BadResponseError):
        openai_client(reply(body)).chat(HISTORY)


def test_openai_empty_choices_is_a_bad_response():
    with pytest.raises(BadResponseError):
        openai_client(reply({"choices": []})).chat(HISTORY)


# ---- HTTP error mapping (shared) ----
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (500, ProviderUnavailable),
        (503, ProviderUnavailable),
        (400, InvalidRequestError),
        (404, InvalidRequestError),
    ],
)
def test_http_errors_map_to_our_errors(status, error):
    with pytest.raises(error):
        openai_client(reply({"error": "x"}, status)).chat(HISTORY)


def test_timeout_and_network_errors_are_unavailable():
    def timeout(request):
        raise httpx.ReadTimeout("slow")

    def down(request):
        raise httpx.ConnectError("no route")

    for handler in (timeout, down):
        with pytest.raises(ProviderUnavailable):
            openai_client(handler).chat(HISTORY)


def test_non_json_body_is_a_bad_response():
    with pytest.raises(BadResponseError):
        openai_client(lambda r: httpx.Response(200, text="<html>")).chat(HISTORY)


def test_repr_never_contains_the_key():
    assert "secret-key" not in repr(
        OpenAICompatClient(name="groq", api_key="secret-key", model="m", base_url="https://x.test")
    )


# ---- Gemini ----
def gemini_client(handler):
    return GeminiClient(
        api_key="gk", model="gem", base_url="https://g.test/v1beta", http=http(handler)
    )


def test_gemini_request_shape():
    seen = {}

    def handler(request):
        seen["url"], seen["key"] = str(request.url), request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "تمام"}]}, "finishReason": "STOP"}]
            },
        )

    r = gemini_client(handler).chat(HISTORY, [TOOL], temperature=0.1, max_tokens=64)
    body = seen["body"]
    assert seen["url"] == "https://g.test/v1beta/models/gem:generateContent"
    assert "gk" not in seen["url"] and seen["key"] == "gk"  # key travels in a header only
    assert body["systemInstruction"]["parts"][0]["text"] == "You are the support agent."
    assert body["contents"] == [{"role": "user", "parts": [{"text": "فين طلبي 10001؟"}]}]
    assert body["generationConfig"] == {"temperature": 0.1, "maxOutputTokens": 64}
    declaration = body["tools"][0]["functionDeclarations"][0]
    assert (
        declaration["name"] == "order_get"
        and "additionalProperties" not in declaration["parameters"]
    )
    assert r.text == "تمام" and r.finish_reason == "stop" and r.provider == "gemini"


def test_gemini_function_call_keeps_provider_data_for_the_next_turn():
    part = {
        "functionCall": {"name": "order_get", "args": {"order_id": 10001}},
        "thoughtSignature": "sig-1",
    }
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [part]}}],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 1},
            },
        )

    c = gemini_client(handler)
    r = c.chat(HISTORY, [TOOL])
    (call,) = r.tool_calls
    assert r.finish_reason == "tool_calls" and call.arguments == {"order_id": 10001}
    assert call.id and call.provider_data == part
    assert (r.usage.input_tokens, r.usage.output_tokens) == (5, 1)

    c.chat(
        [
            *HISTORY,
            Message("assistant", tool_calls=(call,)),
            Message(
                "tool", '{"ok": true, "status": "shipped"}', tool_call_id=call.id, name="order_get"
            ),
        ]
    )
    contents = bodies[-1]["contents"]
    assert contents[1] == {"role": "model", "parts": [part]}  # signature sent back untouched
    assert contents[2] == {
        "role": "user",
        "parts": [
            {
                "functionResponse": {
                    "name": "order_get",
                    "response": {"ok": True, "status": "shipped"},
                }
            }
        ],
    }


def test_gemini_calls_from_another_provider_get_a_placeholder_signature():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "x"}]}}]})

    foreign = ToolCall("c1", "order_get", {"order_id": 1})  # made by Groq: no provider_data
    gemini_client(handler).chat([*HISTORY, Message("assistant", tool_calls=(foreign,))])
    part = seen["body"]["contents"][1]["parts"][0]
    assert part == {
        "functionCall": {"name": "order_get", "args": {"order_id": 1}},
        "thoughtSignature": SKIP_SIGNATURE,
    }


def test_gemini_parallel_tool_results_share_one_turn():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "x"}]}}]})

    calls = (
        ToolCall("a", "order_get", {"order_id": 1}),
        ToolCall("b", "order_get", {"order_id": 2}),
    )
    gemini_client(handler).chat(
        [
            *HISTORY,
            Message("assistant", tool_calls=calls),
            Message("tool", "[1]", tool_call_id="a", name="order_get"),
            Message("tool", "plain", tool_call_id="b", name="order_get"),
        ]
    )
    last = seen["body"]["contents"][-1]
    assert last["role"] == "user" and len(last["parts"]) == 2
    assert last["parts"][0]["functionResponse"]["response"] == {"result": [1]}
    assert last["parts"][1]["functionResponse"]["response"] == {"result": "plain"}


def test_gemini_skips_thought_parts_and_maps_max_tokens():
    body = {
        "candidates": [
            {
                "content": {"parts": [{"text": "thinking", "thought": True}, {"text": "answer"}]},
                "finishReason": "MAX_TOKENS",
            }
        ]
    }
    r = gemini_client(reply(body)).chat(HISTORY)
    assert r.text == "answer" and r.finish_reason == "length"


def test_gemini_blocked_prompt_is_a_bad_response():
    with pytest.raises(BadResponseError, match="SAFETY"):
        gemini_client(reply({"promptFeedback": {"blockReason": "SAFETY"}})).chat(HISTORY)


def test_clean_schema_removes_unsupported_keys_everywhere():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"a": {"type": "array", "items": {"type": "string", "default": "x"}}},
    }
    assert clean_schema(schema) == {
        "type": "object",
        "properties": {"a": {"type": "array", "items": {"type": "string"}}},
    }


# ---- Anthropic ----
def test_anthropic_round_trip():
    seen = []

    def handler(request):
        seen.append(
            (
                request.headers["x-api-key"],
                request.headers["anthropic-version"],
                json.loads(request.content),
            )
        )
        return httpx.Response(
            200,
            json={
                "model": "claude-x",
                "content": [
                    {"type": "text", "text": "بشوف"},
                    {
                        "type": "tool_use",
                        "id": "tu1",
                        "name": "order_get",
                        "input": {"order_id": 10002},
                    },
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 9, "output_tokens": 3},
            },
        )

    c = AnthropicClient(
        api_key="ak", model="claude-x", base_url="https://a.test/v1", http=http(handler)
    )
    r = c.chat(HISTORY, [TOOL])
    key, version, body = seen[0]
    assert key == "ak" and version and body["system"] == "You are the support agent."
    assert body["tools"][0]["input_schema"]["type"] == "object"
    (call,) = r.tool_calls
    assert r.text == "بشوف" and r.finish_reason == "tool_calls" and call.id == "tu1"

    c.chat(
        [
            *HISTORY,
            Message("assistant", "بشوف", (call,)),
            Message("tool", '{"ok": true}', tool_call_id="tu1", name="order_get"),
        ]
    )
    msgs = seen[1][2]["messages"]
    assert msgs[1]["content"][1] == {
        "type": "tool_use",
        "id": "tu1",
        "name": "order_get",
        "input": {"order_id": 10002},
    }
    assert msgs[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": '{"ok": true}'}],
    }


# ---- Fallback chain ----
class Stub:
    def __init__(self, name, *, error=None):
        self.name, self.error, self.calls = name, error, 0

    def chat(self, messages, tools=(), *, temperature=0.2, max_tokens=1024):
        self.calls += 1
        if self.error:
            raise self.error
        from ai_commerce_marketplace.llm import LLMResponse, Usage

        return LLMResponse(f"from {self.name}", (), "stop", Usage(), self.name, "m")


def test_fallback_uses_the_primary_when_it_works():
    a, b = Stub("gemini"), Stub("groq")
    r = FallbackClient([a, b]).chat(HISTORY)
    assert r.provider == "gemini" and r.failed_providers == () and b.calls == 0


def test_fallback_moves_to_the_next_provider_and_reports_who_failed():
    a, b = Stub("gemini", error=RateLimitError("429")), Stub("groq")
    r = FallbackClient([a, b]).chat(HISTORY)
    assert r.provider == "groq" and r.failed_providers == ("gemini: rate_limited",)


def test_fallback_goes_down_the_whole_chain():
    chain = FallbackClient(
        [
            Stub("gemini", error=ProviderUnavailable("down")),
            Stub("groq", error=AuthenticationError("bad key")),
            Stub("openrouter"),
        ]
    )
    r = chain.chat(HISTORY)
    assert r.provider == "openrouter"
    assert r.failed_providers == ("gemini: unavailable", "groq: auth_failed")


def test_fallback_stops_on_our_own_invalid_request():
    a, b = Stub("gemini", error=InvalidRequestError("bad schema")), Stub("groq")
    with pytest.raises(InvalidRequestError):
        FallbackClient([a, b]).chat(HISTORY)
    assert b.calls == 0


def test_fallback_raises_when_every_provider_fails():
    chain = FallbackClient(
        [Stub("gemini", error=RateLimitError("x")), Stub("groq", error=BadResponseError("y"))]
    )
    with pytest.raises(AllProvidersFailed, match="gemini: rate_limited; groq: bad_response"):
        chain.chat(HISTORY)


def test_no_providers_is_a_clear_error():
    with pytest.raises(NotConfiguredError):
        FallbackClient([]).chat(HISTORY)


# ---- factory ----
def test_factory_keeps_the_configured_order_and_skips_missing_keys():
    chain = build_llm_client(
        ["gemini", "groq", "openrouter"],
        {"gemini": "g", "groq": None, "openrouter": "o"},
        models={"openrouter": "my/model"},
    )
    assert [c.name for c in chain.clients] == ["gemini", "openrouter"]
    assert chain.clients[1].model == "my/model"


def test_factory_without_any_key_builds_an_empty_chain():
    with pytest.raises(NotConfiguredError):
        build_llm_client(["gemini"], {}).chat(HISTORY)


def test_factory_supports_every_provider_kind():
    keys = dict.fromkeys(["gemini", "groq", "xai", "openrouter", "openai", "anthropic"], "k")
    chain = build_llm_client(list(keys), keys)
    assert [type(c).__name__ for c in chain.clients] == [
        "GeminiClient",
        "OpenAICompatClient",
        "OpenAICompatClient",
        "OpenAICompatClient",
        "OpenAICompatClient",
        "AnthropicClient",
    ]


def test_provider_list_parsing_aliases_and_dedupe():
    assert parse_provider_list("Gemini, grok ,openrouter,gemini") == ["gemini", "xai", "openrouter"]
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        parse_provider_list("gemini,llama-cpp")


def test_get_llm_client_reads_the_settings(monkeypatch):
    from ai_commerce_marketplace.core.config import settings
    from ai_commerce_marketplace.llm import get_llm_client

    monkeypatch.setattr(settings, "llm_providers", "gemini,grok")
    monkeypatch.setattr(settings, "gemini_api_key", "g")
    monkeypatch.setattr(settings, "xai_api_key", "x")
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "llm_models", {"gemini": "my-gemini"})
    get_llm_client.cache_clear()
    try:
        chain = get_llm_client()
        assert [(c.name, c.model) for c in chain.clients][0] == ("gemini", "my-gemini")
        assert [c.name for c in chain.clients] == ["gemini", "xai"]
    finally:
        get_llm_client.cache_clear()
