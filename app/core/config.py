import re
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated environment configuration shared by every process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "NexusAI"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    public_base_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://nexusai:nexusai@localhost:5432/nexusai"
    redis_url: str = "redis://localhost:6379/0"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)

    telegram_bot_token: SecretStr = SecretStr("replace-me")
    telegram_webhook_secret: SecretStr = SecretStr("replace-me-with-random-token")
    telegram_webhook_path: str = "/webhooks/telegram"
    telegram_max_connections: int = Field(default=40, ge=1, le=100)
    telegram_drop_pending_updates: bool = False

    openai_api_key: SecretStr = SecretStr("replace-me")
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = Field(default=45.0, gt=1, le=180)
    openai_max_output_tokens: int = Field(default=800, ge=64, le=8000)
    chat_history_messages: int = Field(default=12, ge=2, le=50)
    max_user_message_chars: int = Field(default=4000, ge=100, le=16000)

    free_daily_messages: int = Field(default=10, ge=0, le=10000)
    premium_daily_messages: int = Field(default=500, ge=1, le=100000)
    rate_limit_requests: int = Field(default=8, ge=1, le=1000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    admin_username: str = "admin"
    admin_password_hash: SecretStr = SecretStr("replace-with-argon2-hash")
    secret_key: SecretStr = SecretStr("replace-with-64-random-characters")
    cookie_secure: bool = False
    admin_session_minutes: int = Field(default=60, ge=5, le=1440)

    scheduler_enabled: bool = True
    news_refresh_minutes: int = Field(default=30, ge=5, le=1440)
    news_feed_urls: str = "https://openai.com/news/rss.xml,https://www.anthropic.com/news/rss.xml"
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    premium_monthly_price_cents: int = Field(default=999, ge=0)
    premium_currency: str = "USD"
    telegram_payment_provider_token: SecretStr | None = None

    @field_validator("public_base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("telegram_webhook_path")
    @classmethod
    def normalize_webhook_path(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://") and "+asyncpg" not in value:
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def validate_secure_production_settings(self) -> "Settings":
        """Fail fast when production is configured with insecure placeholders."""
        webhook_secret = self.telegram_webhook_secret.get_secret_value()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", webhook_secret):
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET must contain only letters, digits, underscores, "
                "and hyphens and be 1-256 characters long"
            )

        if self.environment != "production":
            return self

        secret_values = {
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token.get_secret_value(),
            "OPENAI_API_KEY": self.openai_api_key.get_secret_value(),
            "ADMIN_PASSWORD_HASH": self.admin_password_hash.get_secret_value(),
            "SECRET_KEY": self.secret_key.get_secret_value(),
        }
        placeholders = {name for name, value in secret_values.items() if "replace" in value.lower()}
        if placeholders:
            names = ", ".join(sorted(placeholders))
            raise ValueError(f"Production secrets still contain placeholders: {names}")
        if not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must use HTTPS in production")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if self.admin_username.lower() == "admin":
            raise ValueError("ADMIN_USERNAME must not use the default value in production")
        if len(secret_values["SECRET_KEY"]) < 64:
            raise ValueError("SECRET_KEY must contain at least 64 characters in production")
        if not secret_values["ADMIN_PASSWORD_HASH"].startswith("$argon2"):
            raise ValueError("ADMIN_PASSWORD_HASH must be an Argon2 hash in production")
        return self

    @property
    def webhook_url(self) -> str:
        return f"{self.public_base_url}{self.telegram_webhook_path}"

    @property
    def parsed_news_feeds(self) -> list[str]:
        return [item.strip() for item in self.news_feed_urls.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
