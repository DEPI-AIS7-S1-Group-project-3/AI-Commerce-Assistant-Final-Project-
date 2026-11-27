"""Try providers in order until one answers."""

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import replace

from ai_commerce_marketplace.llm.base import LLMClient
from ai_commerce_marketplace.llm.errors import (
    AllProvidersFailed,
    LLMError,
    NotConfiguredError,
    ProviderUnavailable,
    RateLimitError,
)
from ai_commerce_marketplace.llm.types import LLMResponse, Message, ToolSpec

log = logging.getLogger(__name__)


class FallbackClient:
    """First client is the primary; the others are used only when the one before it fails.

    A failure that is our own fault (``InvalidRequestError``) is raised straight away,
    because trying another provider would only hide the bug.
    """

    name = "fallback"
    COOLDOWN_S = 20.0  # a provider that just said "rate limited" or "unavailable" rests this long

    def __init__(self, clients: Sequence[LLMClient], clock: Callable[[], float] = time.monotonic):
        self.clients = list(clients)
        self._clock = clock
        self._resting_until: dict[str, float] = {}

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if not self.clients:
            raise NotConfiguredError("No LLM provider is configured (set an API key)")
        failures: list[str] = []
        now = self._clock()
        ready = [c for c in self.clients if self._resting_until.get(c.name, 0.0) <= now]
        for client in ready or self.clients:  # everyone resting: try them all rather than give up
            try:
                resp = client.chat(messages, tools, temperature=temperature, max_tokens=max_tokens)
            except LLMError as e:
                if not e.fallback_ok:
                    raise
                if isinstance(e, RateLimitError | ProviderUnavailable):
                    self._resting_until[client.name] = self._clock() + self.COOLDOWN_S
                failures.append(f"{client.name}: {e.code}")
                log.warning(
                    "LLM provider %s failed (%s): %s. Trying the next one.", client.name, e.code, e
                )
                continue
            return replace(resp, failed_providers=tuple(failures)) if failures else resp
        raise AllProvidersFailed("All LLM providers failed: " + "; ".join(failures))
