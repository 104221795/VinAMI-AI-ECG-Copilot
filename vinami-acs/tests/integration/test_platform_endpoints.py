"""Integration tests for platform-only FastAPI endpoints."""

import os

from apps.api.app import create_app
from fastapi.testclient import TestClient

from vinami.shared.config import Settings


def make_settings() -> Settings:
    """Build an in-memory configuration without an external PostgreSQL dependency."""
    return Settings(database_url="sqlite+pysqlite:///:memory:", identity_mode="development")


def test_health_endpoint_returns_liveness() -> None:
    """Health must not require a database connection."""
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "vinami-acs-api"}


def test_readiness_rejects_connected_database_without_schema() -> None:
    """Connectivity alone must not make an unmigrated database ready."""
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["dependency"] == "postgresql_schema"


def test_readiness_accepts_real_migrated_postgresql(postgres_session_factory: object) -> None:
    """Readiness succeeds only after the production Alembic path reaches expected head."""
    _ = postgres_session_factory
    settings = Settings(database_url=os.environ["VINAMI_DATABASE_URL"], identity_mode="development")
    with TestClient(create_app(settings)) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["revision"] == settings.expected_schema_revision
    assert response.json()["identity"]["mode"] == "development"


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    """Metrics are exported from the application-owned registry."""
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "vinami_http_requests_total" in response.text
