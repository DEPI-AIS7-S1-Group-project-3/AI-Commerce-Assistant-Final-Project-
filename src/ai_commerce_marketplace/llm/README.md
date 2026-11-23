# LLM layer

One interface for every model. Agents and the router depend on `LLMClient` and the neutral
types in `types.py`; they never import a provider module. Changing the model is a config change.

## Providers

| Name | Adapter | Notes |
|---|---|---|
| `gemini` | `gemini.py` | Google generateContent API. Default primary. |
| `groq` | `openai_compat.py` | OpenAI-compatible |
| `xai` (alias `grok`) | `openai_compat.py` | OpenAI-compatible |
| `openrouter` | `openai_compat.py` | OpenAI-compatible |
| `openai` (alias `gpt`) | `openai_compat.py` | OpenAI-compatible |
| `anthropic` (alias `claude`) | `anthropic.py` | Messages API |

Adding another OpenAI-compatible provider is one line in `PROVIDERS` (`factory.py`).

## Configuration (`.env`)

```
LLM_PROVIDERS=gemini,groq,openrouter   # ordered: first = primary, the rest = fallbacks
GEMINI_API_KEY=...
GROQ_API_KEY=...
OPENROUTER_API_KEY=...
LLM_MODELS={"gemini": "gemini-3-flash-preview"}   # optional per-provider model override
LLM_TIMEOUT_S=30
LLM_GEMINI_THINKING=auto   # auto = "low" for Gemini 3 models; none | minimal | low | medium | high
```

A provider with no key is skipped. With no key at all the app still starts, and a call
raises `NotConfiguredError`.

## Usage

```python
from ai_commerce_marketplace.llm import Message, ToolSpec, get_llm_client

llm = get_llm_client()
reply = llm.chat(
    [Message("system", "..."), Message("user", "فين طلبي؟")],
    tools=[ToolSpec("order_get", "One order", {"type": "object", "properties": {...}})],
)
reply.text, reply.tool_calls, reply.provider, reply.failed_providers
```

A tool result goes back as `Message("tool", json_text, tool_call_id=call.id, name=call.name)`,
after the assistant message that carried `tool_calls`.

## Fallback

`FallbackClient` tries providers in order. It moves on after a rate limit, an outage, a timeout,
a bad key or an unusable answer. It stops at once on `InvalidRequestError` (our own request is
wrong, so another provider would only hide the bug). `reply.failed_providers` says who failed.

## Lessons from the first live run

- **Gemini 3 thinks at `high` by default.** That made one short answer take 26 seconds, and the
  thinking tokens count against `max_tokens`, so the reply was cut after a few words
  (`finish=length`). The client now sends `thinkingLevel: low` for `gemini-3*` models
  (`LLM_GEMINI_THINKING` to change it).
- **A provider that does not know the model (HTTP 404) no longer stops the chain.** Groq retired
  `llama-3.3-70b-versatile` on 2026-08-16; the default is now `openai/gpt-oss-120b`. Model names
  change often: set `LLM_MODELS` when a provider answers `model_not_found`.
- The log line for a failed provider now says why, not just the code.

## Notes

- Keys travel in headers only, never in URLs, and are not part of `repr()`.
- Gemini 3 needs a "thought signature" returned with each function call. It is kept in
  `ToolCall.provider_data` and sent back automatically. Calls made by another provider get a
  placeholder, which is documented by Google but is not covered by a live test.
- The client is synchronous, like the services and tools. Wrap it with `run_in_threadpool`
  in async routes.
- Tests use `httpx.MockTransport`: no network, no keys.
