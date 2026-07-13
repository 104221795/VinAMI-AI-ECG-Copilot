"""PostgreSQL-backed acceptance tests for identity binding and endpoint permissions."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from vinami.audit.adapters.persistence import AuditLogRecord
from vinami.identity.adapters.development import DEVELOPMENT_IDENTITIES
from vinami.shared.config import Settings


def _settings() -> Settings:
    return Settings(database_url=os.environ["VINAMI_DATABASE_URL"], identity_mode="development")


def _headers(identity: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "X-Development-Identity": identity,
        "X-Correlation-ID": str(uuid4()),
        "X-Request-Source": "pytest-r1-5",
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _create_case(
    client: TestClient,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    patient = client.post(
        "/api/v1/patients",
        headers=_headers("nurse", f"patient-{uuid4()}"),
        json={"patient_reference": f"R15-{uuid4()}", "safe_demographic_summary": {}},
    )
    assert patient.status_code == 201, patient.text
    encounter = client.post(
        "/api/v1/encounters",
        headers=_headers("nurse", f"encounter-{uuid4()}"),
        json={
            "patient_id": patient.json()["patient_id"],
            "location": "Emergency Department",
            "arrival_at": datetime.now(UTC).isoformat(),
        },
    )
    assert encounter.status_code == 201, encounter.text
    clinical_case = client.post(
        "/api/v1/clinical-cases",
        headers=_headers("nurse", f"case-{uuid4()}"),
        json={
            "encounter_id": encounter.json()["encounter_id"],
            "opening_reason": "R1.5 identity acceptance",
            "priority": "urgent",
        },
    )
    assert clinical_case.status_code == 201, clinical_case.text
    return patient.json(), encounter.json(), clinical_case.json()


def test_missing_invalid_and_unauthorized_identities_return_safe_problems(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings())) as client:
        missing = client.get(f"/api/v1/patients/{uuid4()}")
        invented = client.get(
            f"/api/v1/patients/{uuid4()}",
            headers={"X-Development-Identity": "invented-admin"},
        )
        read_only_mutation = client.post(
            "/api/v1/patients",
            headers=_headers("read_only_reviewer", f"forbidden-{uuid4()}"),
            json={"patient_reference": f"R15-{uuid4()}", "safe_demographic_summary": {}},
        )

    assert missing.status_code == invented.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert read_only_mutation.status_code == 403
    for response in (missing, invented, read_only_mutation):
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["correlation_id"]


def test_verified_actor_overrides_untrusted_actor_headers_and_populates_audit(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    with TestClient(create_app(_settings())) as client:
        malicious_headers = _headers("nurse", f"bound-{uuid4()}")
        malicious_headers["X-Actor-ID"] = str(uuid4())
        malicious_headers["X-Actor-Role"] = "administrator"
        patient = client.post(
            "/api/v1/patients",
            headers=malicious_headers,
            json={"patient_reference": f"R15-{uuid4()}", "safe_demographic_summary": {}},
        )
        assert patient.status_code == 201, patient.text
        _, encounter, clinical_case = _create_case(client)
        technician_open = client.post(
            "/api/v1/clinical-cases",
            headers=_headers("technician", f"forbidden-case-{uuid4()}"),
            json={
                "encounter_id": encounter["encounter_id"],
                "opening_reason": "Must be denied before domain evaluation",
                "priority": "urgent",
            },
        )
        assert technician_open.status_code == 403
        client.app.state.container.event_dispatcher().dispatch_pending()
        audit = client.get(
            f"/api/v1/clinical-cases/{clinical_case['case_id']}/audit",
            headers=_headers("auditor"),
        )

    assert audit.status_code == 200, audit.text
    nurse = DEVELOPMENT_IDENTITIES["nurse"]
    assert audit.json()
    assert all(item["actor_id"] == str(nurse.actor_id) for item in audit.json())
    assert all(item["identity_subject"] == nurse.subject_id for item in audit.json())
    assert all(item["identity_provider"] == "vinami-development" for item in audit.json())
    assert all(item["authentication_method"] == "development_fixture" for item in audit.json())
    assert all(item["applied_permission"] is not None for item in audit.json())

    with postgres_session_factory() as session:
        rejected = session.scalars(
            select(AuditLogRecord).where(
                AuditLogRecord.outcome.in_(["authentication_failure", "authorization_failure"])
            )
        ).all()
        assert rejected


def test_raw_bearer_value_is_not_persisted_in_security_audit(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    raw_token = "raw-secret-token-must-not-be-stored"
    with TestClient(create_app(_settings())) as client:
        response = client.get(
            f"/api/v1/patients/{uuid4()}",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
    assert response.status_code == 401
    with postgres_session_factory() as session:
        records = session.scalars(
            select(AuditLogRecord).where(AuditLogRecord.outcome == "authentication_failure")
        ).all()
        assert records
        assert raw_token not in repr(
            [
                (
                    record.payload,
                    record.session_reference,
                    record.identity_subject,
                )
                for record in records
            ]
        )


def test_auditor_can_read_audit_but_cannot_mutate(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings())) as client:
        _, _, clinical_case = _create_case(client)
        client.app.state.container.event_dispatcher().dispatch_pending()
        read = client.get(
            f"/api/v1/clinical-cases/{clinical_case['case_id']}/audit",
            headers=_headers("auditor"),
        )
        mutate = client.post(
            "/api/v1/patients",
            headers=_headers("auditor", f"auditor-write-{uuid4()}"),
            json={"patient_reference": f"R15-{uuid4()}", "safe_demographic_summary": {}},
        )
    assert read.status_code == 200
    assert mutate.status_code == 403


def test_unimplemented_api_resources_are_not_an_anonymous_bypass(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings())) as client:
        anonymous = client.get("/api/v1/tasks")
        clinical_reader = client.get("/api/v1/tasks", headers=_headers("read_only_reviewer"))
        system_reader = client.get("/api/v1/tasks", headers=_headers("system_service"))
    assert anonymous.status_code == 401
    assert clinical_reader.status_code == 403
    assert system_reader.status_code == 200
