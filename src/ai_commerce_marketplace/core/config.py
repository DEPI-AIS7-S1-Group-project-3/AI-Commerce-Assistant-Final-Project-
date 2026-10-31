from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    jwt_secret: str = "dev-only-change-me"
    cors_origins: list[str] = ["http://localhost:5173"]
    env: str = "development"


settings = Settings()
