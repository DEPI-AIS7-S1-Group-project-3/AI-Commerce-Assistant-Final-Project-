import json
from datetime import date
from pathlib import Path

from ai_commerce_marketplace.agents.support.prompts import build_system_prompt
from ai_commerce_marketplace.agents.support.tools import REGISTRY

EVAL = Path(__file__).resolve().parents[2] / "src/ai_commerce_marketplace/agents/support/eval"


def test_prompt_carries_today():
    assert "2026-11-20" in build_system_prompt(date(2026, 11, 20))


def test_prompt_is_read_only_and_hands_actions_to_order_actions():
    p = build_system_prompt(date(2026, 11, 20))
    assert "قراءة وشرح فقط" in p
    assert "مساعد الطلبات" in p


def test_prompt_never_names_internal_tools():
    p = build_system_prompt(date(2026, 11, 20))
    for name in REGISTRY:
        assert name not in p, f"the prompt must not expose the tool name {name}"
    assert "customer_id" not in p


def test_prompt_explains_every_block_code_the_rules_can_return():
    from ai_commerce_marketplace.services import order_rules

    p = build_system_prompt(date(2026, 11, 20))
    codes = {
        e.code
        for e in (
            order_rules.check_cancel_eligibility(s, None)  # type: ignore[arg-type]
            for s in ("cancelled", "return_requested", "delivered", "shipped")
        )
    }
    codes |= {"not_delivered", "not_returnable", "return_exists", "window_expired"}
    for code in codes:
        assert code in p, code


def test_eval_questions_are_well_formed():
    questions = json.loads((EVAL / "questions.json").read_text(encoding="utf-8"))
    assert [q["id"] for q in questions] == list(range(1, len(questions) + 1))
    for q in questions:
        assert q["tool"] in REGISTRY, q["id"]
        assert q["question"] and q["expected_answer"] and q["expect"], q["id"]


def test_prompt_asks_for_direct_policy_answers_without_field_names():
    p = build_system_prompt(date(2026, 11, 17))
    assert "من غير «عادةً»" in p
    assert "warranty_months" in p  # named only to forbid it
