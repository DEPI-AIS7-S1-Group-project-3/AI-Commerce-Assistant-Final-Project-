"""Rules-first intent routing: pick the agent from the words, with no LLM call.

``route`` returns a ``Decision`` when the signal is clear and ``None`` when it is not. The
caller then asks the LLM for a one-word label (``classify.py``). Role gating comes first: the
role decides which agents exist for this caller, and the message can only choose among those.

All keywords are written in normalized form (see ``normalize_ar``): no diacritics, ة -> ه,
أ/إ/آ -> ا, ى -> ي. They are matched on whole words, or on word starts for a few stems.
"""

import re
from dataclasses import dataclass
from typing import Literal

from ai_commerce_marketplace.nlp.arabic import normalize_ar

Agent = Literal["shopping", "support", "order_actions", "seller"]
Role = Literal["visitor", "customer", "seller"]

ALLOWED: dict[str, tuple[Agent, ...]] = {
    "visitor": ("shopping", "support"),
    "customer": ("shopping", "support", "order_actions"),
    "seller": ("seller",),
}

# Words that ask to change an order (the router must confirm before anything happens).
_ACTION = (
    "الغي",
    "الغيه",
    "الغاء",
    "الغيلي",
    "كنسل",
    "cancel",
    "ارجع",
    "ارجعلي",
    "ارجاع",
    "استرجاع",
    "استرجع",
    "رجع",
    "return",
)
# Words about rules and information: policies, delivery, payment, orders already placed.
_SUPPORT = (
    "ضمان",
    "سياسه",
    "سياسة",
    "شروط",
    "استبدال",
    "مصاريف",
    "الشحن بكام",
    "شحن",
    "توصيل",
    "بيوصل",
    "هيوصل",
    "وصل",
    "فين طلبي",
    "طلبي",
    "طلباتي",
    "الطلب",
    "حاله",
    "تتبع",
    "فاتوره",
    "دفع",
    "الدفع",
    "كاش",
    "استرداد",
    "فلوسي",
    "شكوي",
    "مشكله",
    "تواصل",
    "وقع",
    "اتكسر",
    "اتكسرت",
    "باظ",
    "بايظ",
    "عطلان",
    "تالف",
    "policy",
    "warranty",
    "shipping",
    "delivery",
    "track",
    "refund",
    "order",
)
_SHOPPING = (
    "عايز",
    "عاوز",
    "ابحث",
    "دور",
    "بدور",
    "هدور",
    "ادور",
    "دورلي",
    "لاب",
    "لابات",
    "ميزانيت",
    "ارخص",
    "اغلي",
    "احسن",
    "قارن",
    "مقارنه",
    "رشح",
    "ترشيح",
    "اقترح",
    "موبايل",
    "لابتوب",
    "سماعه",
    "تلفزيون",
    "غساله",
    "ثلاجه",
    "ماركه",
    "منتج",
    "سعر",
    "جنيه",
    "بكام",
    "تقييم",
    "تقييمات",
    "مواصفات",
    "اشتري",
    "ميزانيه",
    "buy",
    "cheapest",
    "compare",
    "recommend",
    "price",
    "phone",
    "laptop",
)
# Words that make a message a rules question even when it also contains an action word.
_POLICY = ("سياسه", "شروط", "ينفع", "ممكن", "policy", "مده", "ازاي", "امتي", "كام يوم")

_ORDER_NUMBER = re.compile(r"\b\d{4,}\b")
# "1000 جنيه", "في حدود 15000", "ميزانيتي 40 الف": money, not an order number
_MONEY = re.compile(
    r"\d[\d,]*\s*(?:جنيه|جم|egp|الف|k)\b|(?:حدود|ميزانيت\w*|تحت|فوق|بسعر|اقل من|اكتر من)\s*\d[\d,]*"
)
_YES_NO_ONLY = re.compile(r"^\W*(لا|لاء|no)\W*$")


@dataclass(frozen=True)
class Decision:
    agent: Agent
    reason: Literal["role", "rule", "followup"]
    detail: str = ""


def _words(text: str) -> list[str]:
    return text.split()


_PREFIXES = ("وال", "بال", "لل", "ال")
_WEAK_SHOPPING = {"بكام", "سعر", "تقييم", "تقييمات", "جنيه"}
# Product names say what the question is about, not what the customer wants to do.
_NOUNS = {
    "موبايل",
    "لابتوب",
    "لاب",
    "لابات",
    "سماعه",
    "تلفزيون",
    "غساله",
    "ثلاجه",
    "ماركه",
    "منتج",
    "phone",
    "laptop",
}
# Rule words: with these, a product noun in the same message is just the topic.
_RULE_WORDS = {"ضمان", "سياسه", "شروط", "استبدال", "مصاريف", "شحن", "توصيل", "استرداد", "فاتوره"}


def _tokens(text: str) -> set[str]:
    """Each word as written and without a leading definite article (الشحن -> شحن)."""
    out: set[str] = set()
    for word in text.split():
        out.add(word)
        for prefix in _PREFIXES:
            if word.startswith(prefix) and len(word) - len(prefix) >= 3:
                out.add(word[len(prefix) :])
                break
    return out


def _hit(text: str, tokens: set[str], keys: tuple[str, ...]) -> list[str]:
    found = []
    for key in keys:
        k = normalize_ar(key)
        if not k:
            continue
        if " " in k:
            if k in text:
                found.append(k)
        elif k in tokens or (len(k) >= 4 and any(t.startswith(k) for t in tokens)):
            found.append(k)
    return found


def route(message: str, role: Role, last_agent: Agent | None = None) -> Decision | None:
    allowed = ALLOWED[role]
    if len(allowed) == 1:
        return Decision(allowed[0], "role")

    text = normalize_ar(message)
    tokens = _tokens(text)
    has_number = bool(_ORDER_NUMBER.search(_MONEY.sub(" ", text)))

    action = _hit(text, tokens, _ACTION)
    support = _hit(text, tokens, _SUPPORT)
    shopping = _hit(text, tokens, _SHOPPING)
    policy = _hit(text, tokens, _POLICY)
    if support and set(shopping) <= _WEAK_SHOPPING:
        shopping = []  # "الشحن بكام" is about shipping, not about a product
    if _RULE_WORDS & set(support) and set(shopping) <= _WEAK_SHOPPING | _NOUNS:
        shopping = []  # "الضمان على الموبايلات" is about warranty, not about buying

    # A visitor cannot change an order: Support explains that signing in is needed.
    if action and "order_actions" not in allowed:
        return Decision("support", "rule", f"action:{action[0]} (visitor)")

    if action:
        # "what is the cancellation policy" is a question about rules, not a request.
        if "سياسه" in policy or "policy" in policy or "شروط" in policy:
            return Decision("support", "rule", "policy question")
        if has_number or not (shopping and not support):
            return Decision("order_actions", "rule", f"action:{action[0]}")

    if support and not shopping:
        return Decision("support", "rule", f"support:{support[0]}")
    if shopping and not support and not set(shopping) <= _NOUNS:  # a bare noun says no intent
        return Decision("shopping", "rule", f"shopping:{shopping[0]}")
    if has_number and not (support or shopping):
        return Decision("support", "rule", "order number")

    # A short follow-up with no signal of its own stays with the last agent.
    if not (support or shopping or action) and last_agent in allowed:
        if len(_words(text)) <= 4 or text.startswith("و "):
            return Decision(last_agent, "followup")  # type: ignore[arg-type]
    return None
