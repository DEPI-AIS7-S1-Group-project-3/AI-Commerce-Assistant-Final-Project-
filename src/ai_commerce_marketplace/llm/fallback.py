"""Try providers in order until one answers."""

import logging
from collections.abc import Sequence
from dataclasses import replace

from ai_commerce_marketplace.llm.base import LLMClient
from ai_commerce_marketplace.llm.errors import AllProvidersFailed, LLMError, NotConfiguredError
from ai_commerce_marketplace.llm.types import LLMResponse, Message, ToolSpec

log = logging.getLogger(__name__)


class FallbackClient:
    """First client is the primary; the others are used only when the one before it fails.

    A failure that is our own fault (``InvalidRequestError``) is raised straight away,
    because trying another provider would only hide the bug.
    """

    name = "fallback"

    def __init__(self, clients: Sequence[LLMClient]):
        self.clients = list(clients)

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
        for client in self.clients:
            try:
                resp = client.chat(messages, tools, temperature=temperature, max_tokens=max_tokens)
            except LLMError as e:
                if not e.fallback_ok:
                    raise
                failures.append(f"{client.name}: {e.code}")
                log.warning("LLM provider %s failed (%s), trying the next one", client.name, e.code)
                continue
            return replace(resp, failed_providers=tuple(failures)) if failures else resp
        raise AllProvidersFailed("All LLM providers failed: " + "; ".join(failures))
