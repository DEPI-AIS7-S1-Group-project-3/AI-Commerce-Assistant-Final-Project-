"""Build the LLM client from configuration.

``LLM_PROVIDERS`` is an ordered list: the first is the primary, the rest are fallbacks.
An entry is ``name`` (uses the default or ``LLM_MODELS`` model) or ``name=model``, so one
provider can appear several times with different models, e.g.
``gemini,groq,openrouter=nvidia/nemotron-3-ultra-550b-a55b:free,openrouter=baidu/ernie-5.5-flash-preview:free``.
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
        "openai", "https://openrouter.ai/api/v1", "nvidia/nemotron-3-ultra-550b-a55b:free"
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


def split_entry(entry: str) -> tuple[str, str | None]:
    """ "openrouter=vendor/model:free" -> ("openrouter", "vendor/model:free")."""
    name, _, model = entry.partition("=")
    return name.strip(), (model.strip() or None)


def parse_provider_list(value: str) -> list[str]:
    entries: list[str] = []
    for raw in value.split(","):
        name, model = split_entry(raw)
        name = ALIASES.get(name.lower(), name.lower())
        if name:
            entries.append(f"{name}={model}" if model else name)
    unknown = [e for e in entries if split_entry(e)[0] not in PROVIDERS]
    if unknown:
        raise ValueError(f"Unknown LLM provider(s) {unknown}; choose from {sorted(PROVIDERS)}")
    return list(dict.fromkeys(entries))  # drop duplicates, keep order


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
    for entry in providers:
        name, entry_model = split_entry(entry)
        spec = PROVIDERS[name]
        key = api_keys.get(name)
        if not key:
            log.info("LLM provider %s skipped: no API key", name)
            continue
        model = entry_model or models.get(name) or spec.default_model
        label = f"{name}:{model}" if entry_model else name  # what shows in logs and traces
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
                    name=label,
                    api_key=key,
                    model=model,
                    base_url=spec.base_url,
                    timeout=timeout,
                    http=http,
                )
            )
    return FallbackClient(clients)


def api_keys_from_settings() -> dict[str, str | None]:
    from ai_commerce_marketplace.core.config import settings

    return {
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "xai": settings.xai_api_key,
        "openrouter": settings.openrouter_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
    }


@lru_cache
def get_llm_client() -> LLMClient:
    """The app-wide client, built once from the settings."""
    from ai_commerce_marketplace.core.config import settings

    return build_llm_client(
        parse_provider_list(settings.llm_providers),
        api_keys_from_settings(),
        models=settings.llm_models,
        timeout=settings.llm_timeout_s,
        gemini_thinking=settings.llm_gemini_thinking,
    )
