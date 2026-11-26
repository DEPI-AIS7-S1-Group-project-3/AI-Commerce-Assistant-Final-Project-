from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-change-me-not-for-production-use"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    env: str = "development"

    # LLM layer. LLM_PROVIDERS is ordered: first = primary, the rest = fallbacks.
    llm_providers: str = "gemini,groq,openrouter"
    llm_timeout_s: float = 30.0
    llm_gemini_thinking: str = "auto"  # auto | none | minimal | low | medium | high
    assistant_debug_trace: bool = False  # return the routing/tool trace in /assistant/chat
    assistant_rate_limit_per_minute: int = 20  # per user (or IP for visitors); 0 = off
    llm_models: dict[str, str] = {}  # per-provider model override, e.g. {"gemini": "..."}
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    xai_api_key: str | None = None  # Grok
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    @model_validator(mode="after")
    def _reject_dev_secret_in_production(self) -> "Settings":
        if self.env == "production" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be changed when ENV=production")
        return self


settings = Settings()
