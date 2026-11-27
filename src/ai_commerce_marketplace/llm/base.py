"""The interface every provider implements, plus the HTTP plumbing they share."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Protocol

import httpx

from ai_commerce_marketplace.llm.errors import (
    AuthenticationError,
    BadResponseError,
    InvalidRequestError,
    LLMError,
    ModelNotFoundError,
    ProviderUnavailable,
    RateLimitError,
)
from ai_commerce_marketplace.llm.types import LLMResponse, Message, ToolSpec

DEFAULT_TIMEOUT_S = 30.0


class LLMClient(Protocol):
    """What the agents depend on. A single provider and the fallback chain both fit."""

    name: str

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...


def raise_for_status(provider: str, resp: httpx.Response) -> None:
    """Map an HTTP error to one of our errors. The body is trimmed; keys are never in it."""
    if resp.status_code < 400:
        return
    detail = f"{provider} HTTP {resp.status_code}: {resp.text[:300]}"
    status = resp.status_code
    if status in (401, 403):
        raise AuthenticationError(detail, provider=provider, status=status)
    if status == 404:
        raise ModelNotFoundError(detail, provider=provider, status=status)
    if status == 429:
        raise RateLimitError(detail, provider=provider, status=status)
    if status == 408 or status >= 500:
        raise ProviderUnavailable(detail, provider=provider, status=status)
    if "tool_use_failed" in resp.text or "Tool call validation failed" in resp.text:
        # The MODEL wrote a malformed tool call (e.g. null for an integer). That is that
        # model's slip, not a bug in our request: let the next provider answer.
        raise BadResponseError(detail, provider=provider, status=status)
    raise InvalidRequestError(detail, provider=provider, status=status)


class HTTPProvider(ABC):
    """Base for adapters that call a provider over HTTPS with httpx."""

    name: str

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT_S,
        http: httpx.Client | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http = http or httpx.Client()

    def __repr__(self) -> str:  # never print the key
        return f"{type(self).__name__}(name={self.name!r}, model={self.model!r})"

    def _post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._http.post(url, headers=headers, json=payload, timeout=self.timeout)
        except httpx.TimeoutException as e:
            raise ProviderUnavailable(f"{self.name} timed out", provider=self.name) from e
        except httpx.TransportError as e:
            raise ProviderUnavailable(
                f"{self.name} network error: {type(e).__name__}", provider=self.name
            ) from e
        raise_for_status(self.name, resp)
        try:
            data = resp.json()
        except ValueError as e:
            raise BadResponseError(f"{self.name} returned invalid JSON", provider=self.name) from e
        if not isinstance(data, dict):
            raise BadResponseError(f"{self.name} returned an unexpected body", provider=self.name)
        return data

    @abstractmethod
    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...


__all__ = ["HTTPProvider", "LLMClient", "LLMError", "raise_for_status"]
