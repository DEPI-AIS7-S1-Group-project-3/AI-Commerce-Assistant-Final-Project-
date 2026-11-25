import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_commerce_marketplace.database.base import Base

ROLES = "('visitor', 'customer', 'seller')"
AGENTS = "('shopping', 'support', 'order_actions', 'seller')"


class Conversation(Base):
    """One chat with the assistant. A visitor's conversation has no user_id."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Text)
    last_agent: Mapped[str | None] = mapped_column(Text)
    # An action waiting for the user's "yes": {"tool", "args"}. Dropped after the expiry.
    pending_action: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    pending_expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(f"role IN {ROLES}", name="role"),
        CheckConstraint(f"last_agent IS NULL OR last_agent IN {AGENTS}", name="last_agent"),
        CheckConstraint(
            "(pending_action IS NULL) = (pending_expires_at IS NULL)", name="pending_pair"
        ),
        Index("ix_conversations_user", "user_id"),
    )


class ChatMessage(Base):
    """One turn of text. Tool results are not replayed to the model; they live in tool_trace."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(Text)
    agent: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    tool_trace: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="role"),
        CheckConstraint(f"agent IS NULL OR agent IN {AGENTS}", name="agent"),
        Index("ix_chat_messages_conversation", "conversation_id", "id"),
    )
