"""Unit tests for typed platform configuration."""

import pytest
from pydantic import ValidationError

from vinami.shared.config import Settings


def test_settings_have_safe_platform_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """The scaffold must identify itself and retain a configurable dependency URL."""
    monkeypatch.delenv("VINAMI_IDENTITY_MODE", raising=False)
    settings = Settings()

    assert settings.app_name == "VinAMI ACS Operating System"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.identity_mode is None


def test_development_identity_mode_is_rejected_in_production() -> None:
    with pytest.raises(ValidationError):
        Settings(app_environment="production", identity_mode="development")


def test_oidc_mode_requires_complete_external_provider_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(identity_mode="oidc")
