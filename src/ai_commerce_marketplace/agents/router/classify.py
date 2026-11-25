"""Ask the LLM for a one-word agent label, only when the rules found nothing clear."""

import json
import re

from ai_commerce_marketplace.agents.router.rules import ALLOWED, Agent, Role
from ai_commerce_marketplace.llm import LLMClient, LLMResponse, Message

_DESCRIPTIONS: dict[str, str] = {
    "shopping": "finding, comparing and asking about products, prices, specs and reviews",
    "support": "policies, shipping, payment, warranty and the status of an existing order",
    "order_actions": "asking to cancel or return an order",
}


def _prompt(allowed: tuple[Agent, ...]) -> str:
    lines = [f'- "{a}": {_DESCRIPTIONS[a]}' for a in allowed if a in _DESCRIPTIONS]
    return (
        "You route a customer message of an online store to one agent. "
        "The message is Egyptian Arabic or English. Reply with JSON only, "
        'like {"agent": "support"}. Agents:\n' + "\n".join(lines)
    )


def classify(
    llm: LLMClient, message: str, role: Role, last_agent: Agent | None
) -> tuple[Agent | None, LLMResponse]:
    """Return the chosen agent (None if the label is not an allowed agent) and the response."""
    allowed = ALLOWED[role]
    hint = f"\nThe previous message was answered by: {last_agent}." if last_agent else ""
    reply = llm.chat(
        [Message("system", _prompt(allowed) + hint), Message("user", message)],
        temperature=0.0,
        max_tokens=40,
    )
    match = re.search(r"\{.*?\}", reply.text, re.S)
    label = None
    if match:
        try:
            label = json.loads(match.group(0)).get("agent")
        except (ValueError, AttributeError):
            label = None
    return (label if label in allowed else None), reply  # type: ignore[return-value]
