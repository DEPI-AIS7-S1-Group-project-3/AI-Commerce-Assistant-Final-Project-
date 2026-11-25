"""Live end-to-end check of the assistant with your real LLM key and the demo data.

    uv run python -m scripts.chat_smoke

Needs a seeded database (see docs/demo-data.md) and GEMINI_API_KEY in .env. It uses the demo
accounts directly (no passwords). It CANCELS demo order 10002 in scenario 3 and commits it, so
run the seed again afterwards to restore the demo data (see docs/demo-data.md).

About 10 LLM calls in total.
"""

import sys

from sqlalchemy import select

from ai_commerce_marketplace.agents.router.graph import handle_chat
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import SessionLocal
from ai_commerce_marketplace.llm import LLMError, get_llm_client


def show(title: str, r) -> None:
    print(f"\n{title}\n  agent={r.agent}  route={r.trace.get('route')}")
    print(f"  tools={[t['tool'] for t in r.trace.get('tools', [])]}")
    print(f"  provider={r.trace.get('provider')}  rounds={r.trace.get('rounds')}")
    print(f"  guard={r.trace.get('guard')}")
    print(f"  reply: {r.reply[:300]}")
    if r.needs_confirmation:
        print(f"  needs_confirmation: {r.needs_confirmation['question'][:120]}")


def main() -> int:
    llm = get_llm_client()
    checks: dict[str, bool] = {}
    with SessionLocal() as s:
        customer = s.scalar(select(User).where(User.email == "customer01@example.com"))
        seller = s.scalar(select(User).where(User.email == "seller1@example.com"))
        if customer is None or seller is None:
            print("Demo users not found: seed the database first (docs/demo-data.md).")
            return 2

        r = handle_chat(s, llm, None, "عايز موبايل سامسونج رخيص")
        show("1. Visitor looks for a phone", r)
        checks["visitor -> shopping, with products"] = r.agent == "shopping" and bool(r.products)

        r = handle_chat(s, llm, None, "الضمان على الموبايلات كام سنة؟")
        show("2. Visitor asks about the warranty", r)
        checks["visitor warranty -> support, no internal field names"] = (
            r.agent == "support" and bool(r.reply) and not r.trace["guard"]["internal_terms"]
        )

        r = handle_chat(s, llm, customer, "ألغي طلب 10002")
        show("3a. Customer asks to cancel order 10002", r)
        asked = r.agent == "order_actions" and r.needs_confirmation is not None
        checks["cancel asks for confirmation"] = asked
        r2 = handle_chat(s, llm, customer, "أيوه", r.conversation_id)
        show("3b. Customer says yes", r2)
        checks["yes cancels the order"] = "تم إلغاء" in r2.reply
        s.commit()

        r = handle_chat(s, llm, customer, "طلب رقم 10001 حالته ايه؟")
        show("4. Customer asks about order 10001 (not theirs)", r)
        leaks = ("جنيه", "ج.م", "طريق", "تسليم", "شحن", "out_for_delivery", "customer03")
        checks["no data of another customer's order"] = not any(w in r.reply for w in leaks)

        r = handle_chat(s, llm, seller, "مبيعاتي آخر 30 يوم كام؟")
        show("5. Seller asks about sales", r)
        checks["seller -> seller agent"] = r.agent == "seller"
        s.rollback()

    print()
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LLMError as e:
        print(f"\nLLM error ({e.code}): {e}")
        sys.exit(2)
