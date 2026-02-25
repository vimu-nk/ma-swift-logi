"""Base configuration using Pydantic Settings.

All service-specific settings should inherit from ``BaseServiceSettings``.
Values are loaded from environment variables and .env files.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Common settings shared across all SwiftTrack services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ───────────────────────────────
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    service_name: str = "swifttrack"
    service_port: int = 8000

    # ── RabbitMQ ──────────────────────────────
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    # ── JWT ───────────────────────────────────
    jwt_secret_key: str = "CHANGE-ME"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def json_logs(self) -> bool:
        return self.is_production
