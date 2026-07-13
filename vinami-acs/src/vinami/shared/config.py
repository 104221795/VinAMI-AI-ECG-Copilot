"""Typed runtime configuration for the VinAMI ACS scaffold."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from vinami.shared.schema import EXPECTED_ALEMBIC_HEAD


class Settings(BaseSettings):
    """Read platform configuration from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="VINAMI_", extra="ignore")

    app_name: str = "VinAMI ACS Operating System"
    app_environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://vinami:vinami@localhost:5432/vinami_acs"
    )
    redis_url: str = "redis://localhost:6379/0"
    dashboard_api_base_url: str = "http://api:8000"
    log_level: str = "INFO"
    event_max_retries: int = Field(default=3, ge=1)
    event_retry_delay_seconds: float = Field(default=1.0, ge=0.0)
    event_claim_ttl_seconds: float = Field(default=60.0, gt=0.0)
    event_dispatch_interval_seconds: float = Field(default=1.0, gt=0.0)
    expected_schema_revision: str = EXPECTED_ALEMBIC_HEAD
