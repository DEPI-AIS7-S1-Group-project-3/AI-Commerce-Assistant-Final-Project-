"""Provider-neutral LLM layer. Agents import from here and never from a provider module."""

from ai_commerce_marketplace.llm.base import LLMClient
from ai_commerce_marketplace.llm.errors import (
    AllProvidersFailed,
    AuthenticationError,
    BadResponseError,
    InvalidRequestError,
    LLMError,
    ModelNotFoundError,
    NotConfiguredError,
    ProviderUnavailable,
    RateLimitError,
)
from ai_commerce_marketplace.llm.factory import build_llm_client, get_llm_client
from ai_commerce_marketplace.llm.types import LLMResponse, Message, ToolCall, ToolSpec, Usage

__all__ = [
    "AllProvidersFailed",
    "AuthenticationError",
    "BadResponseError",
    "InvalidRequestError",
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "Message",
    "ModelNotFoundError",
    "NotConfiguredError",
    "ProviderUnavailable",
    "RateLimitError",
    "ToolCall",
    "ToolSpec",
    "Usage",
    "build_llm_client",
    "get_llm_client",
]
