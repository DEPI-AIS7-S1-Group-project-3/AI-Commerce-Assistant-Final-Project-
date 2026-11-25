"""Score the router on the eval set with your real LLM key.

    uv run python -m scripts.router_eval

Rule cases cost no tokens. LLM cases (about 6) ask the model for a label, one call each.
Prints the messages the router got wrong and exits 1 if accuracy is below 90%.
"""

import json
import sys
from pathlib import Path

from ai_commerce_marketplace.agents.router.classify import classify
from ai_commerce_marketplace.agents.router.rules import route
from ai_commerce_marketplace.llm import LLMError, get_llm_client

EVAL = (
    Path(__file__).resolve().parents[1]
    / "src/ai_commerce_marketplace/agents/router/eval/messages.json"
)


def main() -> int:
    cases = json.loads(EVAL.read_text(encoding="utf-8"))
    llm = None
    wrong: list[str] = []
    for c in cases:
        decision = route(c["message"], c["role"], c["last_agent"])
        if decision is not None:
            got, how = decision.agent, "rule"
        else:
            try:
                llm = llm or get_llm_client()
                got, _ = classify(llm, c["message"], c["role"], c["last_agent"])
            except LLMError as e:
                print(f"LLM error ({e.code}): {e}")
                return 2
            how = "llm"
        ok = got in c["expected"]
        print(f"{'PASS' if ok else 'FAIL'} [{how:4}] {c['message']!r} -> {got}")
        if not ok:
            wrong.append(f"{c['message']!r}: got {got}, wanted {c['expected']}")
    right = len(cases) - len(wrong)
    print(f"\n{right}/{len(cases)} correct ({100 * right // len(cases)}%)")
    for line in wrong:
        print("  wrong:", line)
    return 0 if right / len(cases) >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
