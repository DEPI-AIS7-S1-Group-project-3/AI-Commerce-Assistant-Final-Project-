"""Check every model in LLM_PROVIDERS with a real tool-calling request.

    uv run python -m scripts.llm_probe

For each entry (``gemini``, ``groq``, ``openrouter=vendor/model:free`` ...) it sends one request
with a tiny tool and prints whether the model (1) answered, (2) called the tool with a proper
integer argument, (3) how long it took. A model that cannot call tools is useless as a
fallback for the agents, so run this before putting a new model in LLM_PROVIDERS.
"""

import sys
import time

from ai_commerce_marketplace.core.config import settings
from ai_commerce_marketplace.llm import LLMError, Message, ToolSpec
from ai_commerce_marketplace.llm.factory import (
    api_keys_from_settings,
    build_llm_client,
    parse_provider_list,
    split_entry,
)

TOOL = ToolSpec(
    "order_get",
    "Get one order by its number.",
    {
        "type": "object",
        "properties": {"order_id": {"type": "integer", "description": "The order number."}},
        "required": ["order_id"],
    },
)
PROMPT = [
    Message("system", "You are a support assistant. Use the tools to answer."),
    Message("user", "طلب 10002 وصل فين؟"),
]


def main() -> int:
    keys = api_keys_from_settings()
    entries = parse_provider_list(settings.llm_providers)
    worst = 0
    for entry in entries:
        name, _ = split_entry(entry)
        if not keys.get(name):
            print(f"SKIP  {entry}: no API key for {name}")
            continue
        client = build_llm_client(
            [entry], keys, models=settings.llm_models, timeout=settings.llm_timeout_s
        )
        began = time.monotonic()
        try:
            r = client.chat(PROMPT, [TOOL], max_tokens=400)
        except LLMError as e:
            print(f"FAIL  {entry}: {e.code}: {str(e)[:140]}")
            worst = 1
            continue
        took = time.monotonic() - began
        call = r.tool_calls[0] if r.tool_calls else None
        if call and call.name == "order_get" and isinstance(call.arguments.get("order_id"), int):
            print(f"OK    {entry}: called order_get({call.arguments}) in {took:.1f}s")
        elif call:
            print(f"WEAK  {entry}: tool call with odd arguments {call.arguments}")
            worst = 1
        else:
            print(f"NOTOOL {entry}: answered in text only ({r.text[:60]!r}), no tool call")
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main())
