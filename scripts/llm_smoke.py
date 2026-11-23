"""Live check of the LLM layer with your real API keys.

    uv run python -m scripts.llm_smoke

Reads the same settings as the app (.env): LLM_PROVIDERS, GEMINI_API_KEY, ...
Three calls, a few hundred tokens in total, so it fits a free tier. Keys are never printed.
"""

import json
import sys
import time

from ai_commerce_marketplace.llm import (
    LLMClient,
    LLMError,
    LLMResponse,
    Message,
    ToolSpec,
    get_llm_client,
)

ORDER_TOOL = ToolSpec(
    name="order_get",
    description="Status of one customer order, by its number.",
    parameters={
        "type": "object",
        "properties": {"order_id": {"type": "integer", "description": "The order number"}},
        "required": ["order_id"],
    },
)
FAKE_ORDER = {"ok": True, "order_id": 10002, "status": "confirmed", "total_egp": "2359.00"}


def show(r: LLMResponse, started: float) -> None:
    print(f"  provider={r.provider} model={r.model} {time.monotonic() - started:.1f}s")
    print(f"  tokens in/out: {r.usage.input_tokens}/{r.usage.output_tokens}")
    if r.failed_providers:
        print(f"  fell back after: {', '.join(r.failed_providers)}")
    print(f"  finish={r.finish_reason}  text={r.text.strip()[:200]!r}")


def run(llm: LLMClient) -> int:
    system = Message(
        "system",
        "You are a support assistant for an Egyptian online store. "
        "Reply in Egyptian Arabic, briefly.",
    )

    print("1. Plain Arabic answer")
    started = time.monotonic()
    r = llm.chat([system, Message("user", "اهلا، انتوا بتشحنوا لاسكندرية؟")], max_tokens=500)
    show(r, started)
    ok_plain = bool(r.text.strip())

    print("2. Tool call (the model must ask for order 10002)")
    started = time.monotonic()
    history = [system, Message("user", "طلب رقم 10002 حالته ايه؟")]
    r = llm.chat(history, [ORDER_TOOL], max_tokens=500)
    show(r, started)
    call = r.tool_calls[0] if r.tool_calls else None
    ok_call = bool(call and call.name == "order_get" and call.arguments.get("order_id") == 10002)
    print(f"  tool call: {call.name if call else None} {call.arguments if call else ''}")

    ok_final = False
    if call:
        print("3. Tool result goes back, the model answers from it")
        started = time.monotonic()
        history += [
            Message("assistant", r.text, (call,)),
            Message("tool", json.dumps(FAKE_ORDER), tool_call_id=call.id, name=call.name),
        ]
        r = llm.chat(history, [ORDER_TOOL], max_tokens=600)
        show(r, started)
        ok_final = "2359" in r.text and not r.tool_calls
        print(f"  answer uses the tool's total (2359): {ok_final}")

    results = {"plain answer": ok_plain, "tool call": ok_call, "answer from tool result": ok_final}
    print()
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(results.values()) else 1


def main() -> int:
    try:
        return run(get_llm_client())
    except LLMError as e:
        print(f"\nLLM error ({e.code}): {e}")
        if e.code == "not_configured":
            print("Set GEMINI_API_KEY (and optionally GROQ_API_KEY, OPENROUTER_API_KEY) in .env")
        return 2


if __name__ == "__main__":
    sys.exit(main())
