"""Pick the product cards that match what the answer actually says.

The model may search several times and then recommend only some of what it found. The cards
must be those recommended products, in the order the reply mentions them, not simply the
result of the last search (the customer would see text about one laptop and a card of another).
"""

from collections.abc import Sequence
from typing import Any

CARD_LIMIT = 5


def short_name(product: dict[str, Any]) -> str:
    """Brand plus model, e.g. "إتش بي HG5": what a reply calls the product."""
    title = str(product.get("title_ar") or "").split()
    brand = str(product.get("brand") or "").split()
    if brand and title[: len(brand)] == brand and len(title) > len(brand):
        return " ".join(title[: len(brand) + 1])
    return " ".join(title[:2])


def pick_cards(
    reply: str,
    tool_results: Sequence[tuple[str, dict[str, Any]]],
    card_tools: set[str],
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Products named in ``reply`` (in mention order), else ``fallback`` (the last result)."""
    seen: dict[Any, dict[str, Any]] = {}
    for name, res in tool_results:
        if name in card_tools and res.get("ok"):
            for p in res.get("products") or res.get("items") or []:
                if isinstance(p, dict) and p.get("id") is not None:
                    seen.setdefault(p["id"], p)
    text = reply.casefold()
    hits: list[tuple[int, dict[str, Any]]] = []
    for p in seen.values():
        name = short_name(p).casefold()
        pos = text.find(name) if name else -1
        if pos >= 0:
            hits.append((pos, p))
    if not hits:
        return fallback
    return [p for _, p in sorted(hits, key=lambda h: h[0])][:CARD_LIMIT]
