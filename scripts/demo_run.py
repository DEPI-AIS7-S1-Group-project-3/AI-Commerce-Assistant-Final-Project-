"""Run the demo script against the real LLM and the demo data, and print every answer.

    uv run python -m scripts.demo_run                 # print to the terminal
    uv run python -m scripts.demo_run --out demo.md   # also save a Markdown transcript
    uv run python -m scripts.demo_run --pause 4       # wait 4 s between questions

Needs a freshly seeded database (``uv run python -m scripts.demo_reset``) and an LLM key in .env.
It talks to the router directly with the demo accounts (no passwords) and COMMITS the one
cancellation in scene D, so reset the data again before the real demo.

The checks are loose on purpose: they verify the route, the confirmation step and that nothing
leaks or changes when it should not. They do not judge the wording of the answers: read those.
"""

import argparse
import sys
import time
from dataclasses import dataclass

from sqlalchemy import select

from ai_commerce_marketplace.agents.router.cards import short_name
from ai_commerce_marketplace.agents.router.graph import handle_chat
from ai_commerce_marketplace.database.models.order import Order
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import SessionLocal
from ai_commerce_marketplace.llm import LLMError, get_llm_client


@dataclass
class Step:
    actor: str  # visitor | customer | seller
    message: str
    agents: tuple[str, ...]  # accepted agents
    why: str  # what this step shows, for the audience
    products: bool | None = None  # True = must return cards
    confirm: bool | None = None  # True = must ask to confirm, False = must not
    new_chat: bool = False  # start a new conversation for this actor
    needs_tool: str | None = None  # a tool name prefix that must have been called


SCENES: list[tuple[str, list[Step]]] = [
    (
        "A. Visitor shopping (Shopping agent, product cards)",
        [
            Step(
                "visitor",
                "عايز موبايل سامسونج بحدود 15 ألف",
                ("shopping",),
                "Search with a budget and a brand; cards come from the database",
                products=True,
                new_chat=True,
            ),
            Step(
                "visitor",
                "وأيهم كاميرته أحسن؟",
                ("shopping",),
                "A follow-up that only makes sense with the conversation history",
            ),
            Step(
                "visitor",
                "عايز لابتوب للشغل والمونتاج ميزانيتي 40 ألف",
                ("shopping",),
                "A different need in a new conversation",
                products=True,
                new_chat=True,
            ),
            Step(
                "visitor",
                "قارن لي بين أرخص اتنين فيهم",
                ("shopping",),
                "Compare two products from the previous answer",
            ),
        ],
    ),
    (
        "B. Visitor support (Support agent, policies)",
        [
            Step(
                "visitor",
                "الشحن بياخد كام يوم وبكام؟",
                ("support",),
                "Policy answer straight from the policies table",
                new_chat=True,
            ),
            Step(
                "visitor",
                "لو الموبايل جه بايظ أرجّعه إزاي؟",
                ("support",),
                "Returns policy in plain Arabic, no internal field names",
            ),
            Step(
                "visitor",
                "ألغي طلب 10002",
                ("support", "order_actions"),
                "A visitor cannot cancel: the assistant must send them to log in",
                confirm=False,
            ),
        ],
    ),
    (
        "C. Seller (Seller agent, own data only)",
        [
            Step(
                "seller",
                "مبيعاتي آخر 30 يوم كام؟",
                ("seller",),
                "Sales summary from the seller's own orders",
                new_chat=True,
            ),
            Step("seller", "إيه أكتر 3 منتجات بتتباع عندي؟", ("seller",), "Top products"),
            Step("seller", "في منتجات المخزون بتاعها قرب يخلص؟", ("seller",), "Low stock"),
            Step(
                "seller",
                "ألغي طلب 10002",
                ("seller",),
                "A seller cannot cancel a customer's order: Seller agent, order untouched",
                confirm=False,
            ),
        ],
    ),
    (
        "D. Customer (Support + Order Actions, confirmation before any change)",
        [
            Step(
                "customer",
                "طلب 10105 وصل فين؟",
                ("support", "order_actions"),
                "Order tracking for the customer's own order",
                new_chat=True,
            ),
            Step(
                "customer",
                "ألغي طلب 10006",
                ("order_actions",),
                "A delivered order cannot be cancelled: refused with the reason",
                confirm=False,
            ),
            Step(
                "customer",
                "ألغي طلب 10002",
                ("order_actions",),
                "Eligible order: the assistant asks first",
                confirm=True,
            ),
            Step(
                "customer",
                "أيوه",
                ("order_actions",),
                "Only the router's server-side check runs the cancel, never the model",
            ),
            Step(
                "customer",
                "عايز أرجّع طلب 10030",
                ("order_actions",),
                "Return request checked against the return window",
            ),
        ],
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="save a Markdown transcript to this file")
    ap.add_argument("--pause", type=float, default=0.0, help="seconds to wait between questions")
    args = ap.parse_args()

    llm = get_llm_client()
    results: list[tuple[str, bool]] = []
    md: list[str] = ["# Demo transcript\n"]
    with SessionLocal() as s:
        users = {
            "customer": s.scalar(select(User).where(User.email == "customer01@example.com")),
            "seller": s.scalar(select(User).where(User.email == "seller1@example.com")),
            "visitor": None,
        }
        if users["customer"] is None or users["seller"] is None:
            print("Demo users not found: run `uv run python -m scripts.demo_reset` first.")
            return 2
        if s.scalar(select(Order.status).where(Order.id == 10002)) != "confirmed":
            print(
                "Order 10002 is not 'confirmed': run `uv run python -m scripts.demo_reset` first."
            )
            return 2

        convs: dict[str, str | None] = {}
        n = 0
        for scene, steps in SCENES:
            print(f"\n{'=' * 78}\n{scene}\n{'=' * 78}")
            md.append(f"\n## {scene}\n")
            for st in steps:
                n += 1
                if st.new_chat:
                    convs[st.actor] = None
                try:
                    r = handle_chat(s, llm, users[st.actor], st.message, convs.get(st.actor))
                except LLMError as e:  # one bad provider day must not stop the whole run
                    s.rollback()
                    print(f"\n[{n:02d}] {st.actor.upper()}: {st.message}")
                    print(f"     FAIL: LLM error ({e.code}): {str(e)[:160]}")
                    results.append((f"{n:02d} {st.message}", False))
                    md.append(f"**{st.actor}:** {st.message}  \n> LLM error ({e.code})\n")
                    if args.pause:
                        time.sleep(args.pause)
                    continue
                convs[st.actor] = r.conversation_id
                s.commit()  # like the API: each answer is saved on its own

                guard = r.trace.get("guard", {})
                problems = []
                if r.agent not in st.agents:
                    problems.append(f"agent {r.agent}, expected {'/'.join(st.agents)}")
                if st.products and not r.products:
                    problems.append("no product cards")
                stray = [
                    short_name(p)
                    for p in r.products
                    if short_name(p).casefold() not in r.reply.casefold()
                ]
                if stray:
                    problems.append(f"cards the reply never mentions: {stray}")
                if st.confirm is True and r.needs_confirmation is None:
                    problems.append("no confirmation asked")
                if st.confirm is False and r.needs_confirmation is not None:
                    problems.append("asked for confirmation when it must not")
                called = [t["tool"] for t in r.trace.get("tools", [])]
                if st.needs_tool and not any(c.startswith(st.needs_tool) for c in called):
                    problems.append(f"answered without calling a {st.needs_tool}* tool")
                if guard.get("leaked") or guard.get("internal_terms"):
                    problems.append(f"guard flagged: {guard}")
                ok = not problems
                results.append((f"{n:02d} {st.message}", ok))

                print(f"\n[{n:02d}] {st.actor.upper()}: {st.message}")
                print(f"     shows: {st.why}")
                print(
                    f"     agent={r.agent}  provider={r.trace.get('provider')}  "
                    f"tools={[t['tool'] for t in r.trace.get('tools', [])]}"
                )
                print(f"     reply: {r.reply}")
                for p in r.products[:5]:
                    print(f"       - {p['title_ar']}  {p['price_egp']} EGP")
                if r.needs_confirmation:
                    print("     [asks the user to confirm: yes / no buttons]")
                print(f"     {'PASS' if ok else 'FAIL: ' + '; '.join(problems)}")

                md.append(f"**{st.actor}:** {st.message}  \n*{st.why}*  \n> {r.reply}\n")
                md.extend(f"- {p['title_ar']} ({p['price_egp']} EGP)\n" for p in r.products[:5])
                md.append(f"`agent={r.agent}` {'PASS' if ok else 'FAIL'}\n")
                if args.pause:
                    time.sleep(args.pause)

        # State checks at the end: only the customer's own confirmed yes may change data.
        o2 = s.scalar(select(Order.status).where(Order.id == 10002))
        o6 = s.scalar(select(Order.status).where(Order.id == 10006))
        results.append(("order 10002 cancelled only by the customer's yes", o2 == "cancelled"))
        results.append(("delivered order 10006 untouched", o6 == "delivered"))

    print(f"\n{'=' * 78}\nSUMMARY")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(ok for _, ok in results)
    print(
        f"\n{passed}/{len(results)} checks passed. Read the answers: checks do not judge wording."
    )
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        print(f"Transcript saved to {args.out}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LLMError as e:
        print(f"\nLLM error ({e.code}): {e}")
        sys.exit(2)
