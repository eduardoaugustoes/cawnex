"""App configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://cawnex:cawnex@localhost:5433/cawnex"

    # Redis
    redis_url: str = "redis://localhost:6380"

    # Security
    fernet_key: str = ""  # For BYOL key encryption
    github_webhook_secret: str = ""  # For webhook signature verification
    api_key: str = ""  # Simple API key auth for MVP

    # App
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]  # Vite dev server

    model_config = {"env_prefix": "CAWNEX_", "env_file": ".env"}


settings = Settings()
