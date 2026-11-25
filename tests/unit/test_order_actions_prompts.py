from datetime import date

from ai_commerce_marketplace.agents.order_actions.prompts import build_system_prompt


def test_prompt_has_date_and_no_unfilled_placeholders():
    p = build_system_prompt(date(2026, 11, 25))
    assert "2026-11-25" in p
    assert "{" not in p and "}" not in p


def test_cancel_never_asks_for_a_reason_and_calls_the_tool_at_once():
    # Seen live: the model asked "why do you want to cancel?" and the customer's "yes" then
    # confirmed nothing. The tool defaults to customer_request.
    p = build_system_prompt(date(2026, 11, 25))
    assert "متسألش عن السبب أبدًا" in p
    assert "`customer_request`" in p and "`late_delivery`" in p
    assert "فورًا في نفس الدور" in p
