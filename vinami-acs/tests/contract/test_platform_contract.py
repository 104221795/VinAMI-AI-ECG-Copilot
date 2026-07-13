"""Contract-level checks for stable platform endpoint payloads."""

from apps.api.app import create_app
from fastapi.testclient import TestClient

from vinami.shared.config import Settings


def test_health_contract_has_only_public_platform_fields() -> None:
    """Keep the health response small and free of clinical or infrastructure detail."""
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", identity_mode="development")
    with TestClient(create_app(settings)) as client:
        payload = client.get("/health").json()

    assert set(payload) == {"status", "service"}
    assert payload["status"] == "healthy"
