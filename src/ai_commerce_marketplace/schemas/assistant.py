from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=2000)
    conversation_id: str | None = None


class ConfirmationOut(BaseModel):
    question: str


class ChatOut(BaseModel):
    conversation_id: str
    reply: str
    agent: str
    products: list[dict[str, Any]] = []
    needs_confirmation: ConfirmationOut | None = None
    trace: dict[str, Any] | None = None  # development only
