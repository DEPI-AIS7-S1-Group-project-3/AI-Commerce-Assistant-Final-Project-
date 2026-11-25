"""The router eval set, checked offline.

Cases marked ``rule`` must be decided by the rules, with no LLM call. Cases marked ``llm`` must
NOT be decided by the rules (otherwise the rules guess where they should ask). The LLM label
itself is scored by ``scripts/router_eval.py`` with a real key.
"""

import json
from pathlib import Path

import pytest

from ai_commerce_marketplace.agents.router.rules import ALLOWED, route

EVAL = Path(__file__).resolve().parents[2] / (
    "src/ai_commerce_marketplace/agents/router/eval/messages.json"
)
CASES = json.loads(EVAL.read_text(encoding="utf-8"))


def test_eval_is_well_formed():
    assert len(CASES) >= 30
    assert len({c["id"] for c in CASES}) == len(CASES)
    for c in CASES:
        assert c["by"] in {"rule", "llm"}
        assert set(c["expected"]) <= set(ALLOWED[c["role"]]), c  # the role can reach it


@pytest.mark.parametrize("case", [c for c in CASES if c["by"] == "rule"], ids=lambda c: c["id"])
def test_rule_cases(case):
    decision = route(case["message"], case["role"], case["last_agent"])
    assert decision is not None, case["message"]
    assert decision.agent in case["expected"], case["message"]


@pytest.mark.parametrize("case", [c for c in CASES if c["by"] == "llm"], ids=lambda c: c["id"])
def test_llm_cases_are_left_to_the_llm(case):
    assert route(case["message"], case["role"], case["last_agent"]) is None, case["message"]
