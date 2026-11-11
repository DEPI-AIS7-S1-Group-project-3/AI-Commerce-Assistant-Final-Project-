from datetime import date

from ai_commerce_marketplace.agents.seller.prompts import build_system_prompt


def test_prompt_has_dates_and_no_unfilled_placeholders():
    p = build_system_prompt(date(2026, 11, 11))
    assert "2026-11-11" in p
    assert "2026-10-13" in p  # d30 = today - 29
    assert "2026-09-13" in p  # d60 = today - 59
    assert "2026-11-12" in p  # end exclusive
    assert "2026-11-01" in p  # month start
    assert "{" not in p and "}" not in p


def test_prompt_states_the_hard_rules():
    p = build_system_prompt(date(2026, 11, 11))
    assert "قراءة فقط" in p
    assert "seller_id" in p  # mentioned only to forbid revealing it
    assert "تخمين" in p
