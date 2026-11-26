from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ai_commerce_marketplace.agents.router.graph import handle_chat
from ai_commerce_marketplace.api.dependencies import get_optional_user
from ai_commerce_marketplace.api.rate_limit import assistant_limiter
from ai_commerce_marketplace.core.config import settings
from ai_commerce_marketplace.core.exceptions import AppError
from ai_commerce_marketplace.database.models.user import User
from ai_commerce_marketplace.database.session import get_session
from ai_commerce_marketplace.llm import LLMClient, LLMError, get_llm_client
from ai_commerce_marketplace.schemas.assistant import ChatIn, ChatOut

router = APIRouter(prefix="/assistant", tags=["assistant"])


class AssistantUnavailableError(AppError):
    status_code = 503
    code = "assistant_unavailable"
    message = "The assistant is busy. Please try again in a moment."


def get_llm() -> LLMClient:
    return get_llm_client()


@router.post("/chat", response_model=ChatOut)
def chat(
    data: ChatIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    session: Session = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
):
    who = f"user:{user.id}" if user else f"ip:{request.client.host if request.client else '?'}"
    assistant_limiter.check(who, settings.assistant_rate_limit_per_minute)
    try:
        result = handle_chat(session, llm, user, data.message, data.conversation_id)
    except LLMError:
        session.rollback()
        raise AssistantUnavailableError() from None
    session.commit()
    return ChatOut(
        conversation_id=result.conversation_id,
        reply=result.reply,
        agent=result.agent,
        products=result.products,
        needs_confirmation=result.needs_confirmation,  # type: ignore[arg-type]
        trace=result.trace if settings.assistant_debug_trace else None,
    )
