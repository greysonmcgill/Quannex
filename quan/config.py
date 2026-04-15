"""Runtime configuration for Quannex Recovery.

Environment-driven. Loads from ``.env`` during development and from real
environment variables in production. Keep this narrow: every setting here
must be consumed by runtime code in the pilot.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Application ---------------------------------------------------------
    app_name: str = "Quannex Recovery"
    environment: str = "development"
    debug: bool = False

    # -- Database ------------------------------------------------------------
    database_url: str = "sqlite:///./quan.db"

    # -- HTTP CORS (used when not in development mode) ----------------------
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )

    # -- Compliance policy (referenced by compliance engine and UI) ---------
    max_weekly_contact_attempts: int = 7
    contact_hours_start: int = 8
    contact_hours_end: int = 21

    # -- Security ------------------------------------------------------------
    #
    # ``secret_key`` does not ship with a production-safe default. Deployments
    # must set ``SECRET_KEY`` explicitly; otherwise the validator below makes
    # it obvious that the pilot has not been configured.
    secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # -- Optional integrations (resolved lazily where used) -----------------
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("secret_key")
    @classmethod
    def _secret_key_required_in_prod(cls, value: Optional[str], info) -> Optional[str]:
        env = (info.data.get("environment") or "development").lower()
        if env not in {"development", "dev", "local", "test"} and not value:
            raise ValueError(
                "SECRET_KEY must be set outside of development environments."
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """Cached Settings instance."""

    return Settings()


settings = get_settings()
