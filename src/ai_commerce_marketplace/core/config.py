from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-change-me-not-for-production-use"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    jwt_secret: str = DEV_JWT_SECRET
    jwt_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:5173"]
    env: str = "development"

    @model_validator(mode="after")
    def _reject_dev_secret_in_production(self) -> "Settings":
        if self.env == "production" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be changed when ENV=production")
        return self


settings = Settings()
