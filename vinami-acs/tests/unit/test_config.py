"""Unit tests for typed platform configuration."""

from vinami.shared.config import Settings


def test_settings_have_safe_platform_defaults() -> None:
    """The scaffold must identify itself and retain a configurable dependency URL."""
    settings = Settings()

    assert settings.app_name == "VinAMI ACS Operating System"
    assert settings.database_url.startswith("postgresql+psycopg://")
