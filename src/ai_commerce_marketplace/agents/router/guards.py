"""Input and output guardrails for the assistant.

Output rules (checked before a reply is returned):

- the reply must not leak internals: tool names, ``customer_id`` / ``seller_id``, prompt words;
- a reply may only say an order was cancelled or returned if ``execute_confirmed`` returned
  ``done: true`` in this same turn;
- numbers in the reply should come from a tool result of this turn. A mismatch does not block
  the reply; it is listed in the trace so the eval can count it.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ai_commerce_marketplace.nlp.arabic import normalize_ar

MAX_MESSAGE_CHARS = 2000

LEAK_REPLACEMENT = "حصلت مشكلة مؤقتة وأنا بجاوب. ممكن تعيد سؤالك؟"
NO_ACTION_REPLACEMENT = "لسه ما اتعملش أي تغيير على طلبك. لو عايز تلغيه أو ترجّعه قولّي رقم الطلب."

_INTERNAL = re.compile(
    r"customer_id|seller_id|call_tool|execute_confirmed|pending_action|system prompt",
    re.I,
)
_CLAIM = re.compile(
    r"تم\s+(?:ال)?(?:غاء|غي|الغاء)\s|تم\s+(?:ارجاع|تسجيل\s+(?:طلب\s+)?(?:ارجاع|مرتجع))"
    r"|(?:order|it)\s+(?:was|has been)\s+(?:cancelled|canceled|returned)",
    re.I,
)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_JAILBREAK = re.compile(
    r"ignore (?:all |your |previous )|reveal your prompt|system prompt|"
    r"انسي (?:كل )?(?:التعليمات|اللي فات)|اطبع (?:ال)?برومبت|التعليمات اللي معاك",
    re.I,
)


def clean_message(raw: str) -> str:
    """Trim; empty or oversized input is rejected by the caller before any LLM call."""
    return raw.strip()


def looks_like_jailbreak(message: str) -> bool:
    return bool(_JAILBREAK.search(normalize_ar(message)) or _JAILBREAK.search(message))


def _ints(text: str) -> set[int]:
    out: set[int] = set()
    for m in _NUMBER.findall(normalize_ar(re.sub(r"(?<=\d),(?=\d)", "", text))):
        try:
            out.add(int(float(m)))
        except ValueError:
            continue
    return out


@dataclass
class GuardReport:
    leaked: bool = False
    false_action_claim: bool = False
    unsupported_numbers: list[int] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.leaked or self.false_action_claim


def check_reply(
    reply: str,
    tool_results: list[tuple[str, dict[str, Any]]],
    user_message: str,
    tool_names: set[str],
    action_done: bool,
) -> tuple[str, GuardReport]:
    report = GuardReport()
    if _INTERNAL.search(reply) or any(re.search(rf"\b{re.escape(n)}\b", reply) for n in tool_names):
        report.leaked = True
        return LEAK_REPLACEMENT, report
    if not action_done and _CLAIM.search(normalize_ar(reply)):
        report.false_action_claim = True
        return NO_ACTION_REPLACEMENT, report

    known = _ints(user_message)
    for _, result in tool_results:
        known |= _ints(json.dumps(result, ensure_ascii=False, default=str))
    report.unsupported_numbers = sorted(n for n in _ints(reply) if n >= 10 and n not in known)
    return reply, report
