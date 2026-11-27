"""Conversation storage in PostgreSQL (tables ``conversations`` and ``chat_messages``)."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.core.exceptions import NotFoundError
from ai_commerce_marketplace.database.models.conversation import ChatMessage, Conversation
from ai_commerce_marketplace.llm import Message

HISTORY_TURNS = 10
PENDING_TTL = timedelta(minutes=10)


def open_conversation(
    session: Session, conversation_id: str | None, user_id: int | None, role: str
) -> Conversation:
    """Start a conversation, or continue one that belongs to the same user.

    A conversation of someone else, an unknown id and a malformed id all give the same
    ``NotFoundError``, so ids cannot be probed.
    """
    if conversation_id is None:
        conv = Conversation(user_id=user_id, role=role)
        session.add(conv)
        session.flush()
        return conv
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        raise NotFoundError("Conversation not found") from None
    found = session.get(Conversation, cid)
    if found is None or found.user_id != user_id:
        raise NotFoundError("Conversation not found")
    conv = found
    conv.role = role  # the token decides the role, not what was stored
    return conv


def history(session: Session, conv: Conversation) -> list[Message]:
    rows = session.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.id.desc())
        .limit(HISTORY_TURNS * 2)
    ).all()
    return [Message(r.role, _with_shown_note(r)) for r in reversed(rows)]  # type: ignore[arg-type]


def shown_summary(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The few fields of the product cards worth remembering for the next turn."""
    return [
        {"id": p.get("id"), "title_ar": p.get("title_ar"), "price_egp": p.get("price_egp")}
        for p in products[:8]
        if p.get("id") is not None
    ]


def _with_shown_note(row: ChatMessage) -> str:
    """Assistant text plus, for the model only, the ids of the products that card row showed.

    Without it the model cannot tell which ids "the cheaper two" were and starts guessing them.
    """
    content = str(row.content)
    if row.role != "assistant" or not row.tool_trace:
        return content
    shown = row.tool_trace[0].get("shown") if isinstance(row.tool_trace[0], dict) else None
    if not shown:
        return content
    items = "; ".join(
        f"id {p['id']} = {p.get('title_ar')} ({p.get('price_egp')} EGP)" for p in shown
    )
    return (
        f"{content}\n\n[Internal note, never show or quote it to the customer: "
        f"the product cards shown with this answer were: {items}. "
        "Use these ids when the customer refers to them.]"
    )


def live_pending(conv: Conversation, now: datetime) -> dict[str, Any] | None:
    if conv.pending_action is None or conv.pending_expires_at is None:
        return None
    if conv.pending_expires_at <= now:
        clear_pending(conv)
        return None
    return conv.pending_action


def set_pending(conv: Conversation, action: dict[str, Any], now: datetime) -> None:
    conv.pending_action = action
    conv.pending_expires_at = now + PENDING_TTL


def clear_pending(conv: Conversation) -> None:
    conv.pending_action = None
    conv.pending_expires_at = None


def add_turn(
    session: Session,
    conv: Conversation,
    user_text: str,
    reply: str,
    agent: str,
    trace: list[dict[str, Any]],
) -> None:
    session.add(ChatMessage(conversation_id=conv.id, role="user", content=user_text))
    session.add(
        ChatMessage(
            conversation_id=conv.id,
            role="assistant",
            agent=agent,
            content=reply,
            tool_trace=trace,
        )
    )
    conv.last_agent = agent
    session.flush()
