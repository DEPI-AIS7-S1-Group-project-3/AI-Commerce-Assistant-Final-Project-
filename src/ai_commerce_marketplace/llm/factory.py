"""Build the LLM client from configuration.

``LLM_PROVIDERS`` is an ordered list: the first is the primary, the rest are fallbacks.
A provider without an API key is skipped, so the app still starts with no key at all
(a call then raises ``NotConfiguredError``).
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

import httpx

from ai_commerce_marketplace.llm.anthropic import AnthropicClient
from ai_commerce_marketplace.llm.base import DEFAULT_TIMEOUT_S, LLMClient
from ai_commerce_marketplace.llm.fallback import FallbackClient
from ai_commerce_marketplace.llm.gemini import GeminiClient
from ai_commerce_marketplace.llm.openai_compat import OpenAICompatClient

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderSpec:
    kind: str  # "openai" (any OpenAI-compatible API), "gemini" or "anthropic"
    base_url: str
    default_model: str


# Default model names change often: override them with LLM_MODELS instead of editing code.
PROVIDERS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec("gemini", "", "gemini-3-flash-preview"),
    "groq": ProviderSpec("openai", "https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "xai": ProviderSpec("openai", "https://api.x.ai/v1", "grok-4"),
    "openrouter": ProviderSpec(
        "openai", "https://openrouter.ai/api/v1", "openai/gpt-oss-120b:free"
    ),
    "openai": ProviderSpec("openai", "https://api.openai.com/v1", "gpt-5-mini"),
    "anthropic": ProviderSpec("anthropic", "", "claude-sonnet-5-5"),
}
ALIASES = {"grok": "xai", "google": "gemini", "claude": "anthropic", "gpt": "openai"}


def resolve_thinking_level(setting: str, model: str) -> str | None:
    """ "auto" = "low" for Gemini 3 models (they think at "high" by default), nothing for older
    models. "none" sends nothing. Anything else is passed through."""
    value = setting.strip().lower()
    if value in ("none", "off", ""):
        return None
    if value == "auto":
        return "low" if model.startswith("gemini-3") else None
    return value


def parse_provider_list(value: str) -> list[str]:
    names = [ALIASES.get(n.strip().lower(), n.strip().lower()) for n in value.split(",")]
    names = [n for n in names if n]
    unknown = [n for n in names if n not in PROVIDERS]
    if unknown:
        raise ValueError(f"Unknown LLM provider(s) {unknown}; choose from {sorted(PROVIDERS)}")
    return list(dict.fromkeys(names))  # drop duplicates, keep order


def build_llm_client(
    providers: list[str],
    api_keys: Mapping[str, str | None],
    *,
    models: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    http: httpx.Client | None = None,
    gemini_thinking: str = "auto",
) -> LLMClient:
    models = models or {}
    clients: list[LLMClient] = []
    for name in providers:
        spec = PROVIDERS[name]
        key = api_keys.get(name)
        if not key:
            log.info("LLM provider %s skipped: no API key", name)
            continue
        model = models.get(name) or spec.default_model
        if spec.kind == "gemini":
            clients.append(
                GeminiClient(
                    api_key=key,
                    model=model,
                    timeout=timeout,
                    http=http,
                    thinking_level=resolve_thinking_level(gemini_thinking, model),
                )
            )
        elif spec.kind == "anthropic":
            clients.append(AnthropicClient(api_key=key, model=model, timeout=timeout, http=http))
        else:
            clients.append(
                OpenAICompatClient(
                    name=name,
                    api_key=key,
                    model=model,
                    base_url=spec.base_url,
                    timeout=timeout,
                    http=http,
                )
            )
    return FallbackClient(clients)


@lru_cache
def get_llm_client() -> LLMClient:
    """The app-wide client, built once from the settings."""
    from ai_commerce_marketplace.core.config import settings

    return build_llm_client(
        parse_provider_list(settings.llm_providers),
        {
            "gemini": settings.gemini_api_key,
            "groq": settings.groq_api_key,
            "xai": settings.xai_api_key,
            "openrouter": settings.openrouter_api_key,
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
        },
        models=settings.llm_models,
        timeout=settings.llm_timeout_s,
        gemini_thinking=settings.llm_gemini_thinking,
    )
