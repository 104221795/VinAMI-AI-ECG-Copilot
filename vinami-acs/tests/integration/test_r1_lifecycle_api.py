"""PostgreSQL-backed API and projection tests for the R1 lifecycle vertical slice."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from apps.api.app import create_app
from fastapi.testclient import TestClient
from scripts.seed import ACTOR_ID, CASES, SEED_NAMESPACE
from scripts.seed import main as seed_main
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from vinami.audit.adapters.persistence import OutboxEventRecord
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.identity.adapters.persistence import ClinicalUserRecord
from vinami.identity.domain.model import ClinicalRole
from vinami.shared.config import Settings
from vinami.shared.events.contracts import OutboxStatus
from vinami.shared.idempotency_persistence import CommandIdempotencyRecord
from vinami.timeline.adapters.persistence import TimelineEventRecord

NOW = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(database_url=os.environ["VINAMI_DATABASE_URL"])


def _actor(
    postgres_session_factory: sessionmaker[Session], role: ClinicalRole = ClinicalRole.NURSE
) -> UUID:
    actor_id = uuid4()
    with postgres_session_factory() as session:
        session.add(
            ClinicalUserRecord(
                id=actor_id,
                display_name="R1 Development Actor",
                role=role,
                team_id=None,
            )
        )
        session.commit()
    return actor_id


def _headers(actor_id: UUID, key: str, correlation_id: UUID | None = None) -> dict[str, str]:
    return {
        "X-Actor-ID": str(actor_id),
        "X-Actor-Role": "nurse",
        "X-Correlation-ID": str(correlation_id or uuid4()),
        "X-Request-Source": "pytest-r1",
        "Idempotency-Key": key,
    }


def _register(client: TestClient, actor_id: UUID, key: str, reference: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/patients",
        headers=_headers(actor_id, key),
        json={
            "patient_reference": reference,
            "safe_demographic_summary": {"age_band": "45-64", "sex_at_birth": "female"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _lifecycle(
    client: TestClient, actor_id: UUID, suffix: str
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    patient = _register(client, actor_id, f"patient-{suffix}", f"SYN-{suffix}")
    encounter_response = client.post(
        "/api/v1/encounters",
        headers=_headers(actor_id, f"encounter-{suffix}"),
        json={
            "patient_id": patient["patient_id"],
            "location": "Emergency Department",
            "arrival_at": NOW.isoformat(),
            "external_reference": f"ENC-{suffix}",
        },
    )
    assert encounter_response.status_code == 201, encounter_response.text
    encounter = encounter_response.json()
    case_response = client.post(
        "/api/v1/clinical-cases",
        headers=_headers(actor_id, f"case-{suffix}"),
        json={
            "encounter_id": encounter["encounter_id"],
            "opening_reason": "Suspected ACS lifecycle demonstration",
            "priority": "urgent",
        },
    )
    assert case_response.status_code == 201, case_response.text
    return patient, encounter, case_response.json()


def test_all_nine_endpoints_use_persisted_state_and_projections(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    actor_id = _actor(postgres_session_factory)
    correlation_id = uuid4()
    with TestClient(create_app(_settings())) as client:
        patient, encounter, clinical_case = _lifecycle(client, actor_id, str(uuid4()))

        patient_get = client.get(
            f"/api/v1/patients/{patient['patient_id']}",
            headers={"X-Correlation-ID": str(correlation_id)},
        )
        encounter_get = client.get(f"/api/v1/encounters/{encounter['encounter_id']}")
        case_get = client.get(f"/api/v1/clinical-cases/{clinical_case['case_id']}")
        case_list = client.get(
            "/api/v1/clinical-cases",
            params={"priority": "urgent", "location": "Emergency Department"},
        )

        assert patient_get.status_code == encounter_get.status_code == case_get.status_code == 200
        assert patient_get.headers["X-Correlation-ID"] == str(correlation_id)
        assert patient_get.json()["aggregate_version"] == 1
        assert encounter_get.json()["patient_id"] == patient["patient_id"]
        assert case_get.json()["encounter_id"] == encounter["encounter_id"]
        assert any(
            item["case_id"] == clinical_case["case_id"] for item in case_list.json()["items"]
        )

        dispatch = client.app.state.container.event_dispatcher().dispatch_pending()
        assert dispatch.dead_lettered == 0
        timeline = client.get(f"/api/v1/clinical-cases/{clinical_case['case_id']}/timeline")
        audit = client.get(f"/api/v1/clinical-cases/{clinical_case['case_id']}/audit")

        assert [item["event_type"] for item in timeline.json()] == [
            "PatientRegistered.v1",
            "EncounterStarted.v1",
            "ClinicalCaseOpened.v1",
        ]
        assert {item["resource_type"] for item in audit.json()} == {
            "Patient",
            "Encounter",
            "ClinicalCase",
        }
        assert all(item["actor_id"] == str(actor_id) for item in audit.json())
        assert all(item["request_source"] == "pytest-r1" for item in audit.json())


def test_persistent_idempotency_survives_app_restart_and_rejects_payload_change(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    actor_id = _actor(postgres_session_factory)
    key = f"restart-{uuid4()}"
    reference = f"SYN-{uuid4()}"
    with TestClient(create_app(_settings())) as first_client:
        first = _register(first_client, actor_id, key, reference)
    with TestClient(create_app(_settings())) as restarted_client:
        repeated = _register(restarted_client, actor_id, key, reference)
        conflict = restarted_client.post(
            "/api/v1/patients",
            headers=_headers(actor_id, key),
            json={"patient_reference": f"SYN-{uuid4()}", "safe_demographic_summary": {}},
        )
    assert repeated == first
    assert conflict.status_code == 409
    assert conflict.headers["content-type"].startswith("application/problem+json")
    assert conflict.json()["correlation_id"]


def test_concurrent_duplicate_patient_requests_create_one_resource(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    actor_id = _actor(postgres_session_factory)
    key = f"concurrent-{uuid4()}"
    reference = f"SYN-{uuid4()}"
    app_one = create_app(_settings())
    app_two = create_app(_settings())
    with (
        TestClient(app_one) as first_client,
        TestClient(app_two) as second_client,
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        futures = [
            executor.submit(_register, client, actor_id, key, reference)
            for client in (first_client, second_client)
        ]
        results = [future.result(timeout=15) for future in futures]
    assert results[0]["patient_id"] == results[1]["patient_id"]


def test_api_problem_contract_and_active_case_conflict(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    actor_id = _actor(postgres_session_factory)
    with TestClient(create_app(_settings())) as client:
        missing_headers = client.post(
            "/api/v1/patients", json={"patient_reference": f"SYN-{uuid4()}"}
        )
        validation = client.post(
            "/api/v1/patients",
            headers=_headers(actor_id, f"invalid-{uuid4()}"),
            json={"patient_reference": ""},
        )
        missing_parent = client.post(
            "/api/v1/encounters",
            headers=_headers(actor_id, f"missing-{uuid4()}"),
            json={"patient_id": str(uuid4()), "location": "ED", "arrival_at": NOW.isoformat()},
        )
        _, encounter, clinical_case = _lifecycle(client, actor_id, str(uuid4()))
        duplicate_case = client.post(
            "/api/v1/clinical-cases",
            headers=_headers(actor_id, f"duplicate-case-{uuid4()}"),
            json={
                "encounter_id": encounter["encounter_id"],
                "opening_reason": "Duplicate active case",
                "priority": "critical",
            },
        )
        not_found = client.get(f"/api/v1/clinical-cases/{uuid4()}")

    assert missing_headers.status_code == 400
    assert validation.status_code == 422
    assert missing_parent.status_code == 404
    assert duplicate_case.status_code == 409
    assert not_found.status_code == 404
    for response in (missing_headers, validation, missing_parent, duplicate_case, not_found):
        assert set(response.json()) == {
            "type",
            "title",
            "status",
            "detail",
            "instance",
            "correlation_id",
        }
    assert clinical_case["status"] == "open"


def test_openapi_contains_only_real_r1_lifecycle_operations(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings())) as client:
        schema = client.get("/openapi.json").json()
    expected = {
        "/api/v1/patients": {"post"},
        "/api/v1/patients/{patient_id}": {"get"},
        "/api/v1/encounters": {"post"},
        "/api/v1/encounters/{encounter_id}": {"get"},
        "/api/v1/clinical-cases": {"get", "post"},
        "/api/v1/clinical-cases/{case_id}": {"get"},
        "/api/v1/clinical-cases/{case_id}/timeline": {"get"},
        "/api/v1/clinical-cases/{case_id}/audit": {"get"},
    }
    for path, methods in expected.items():
        assert methods <= set(schema["paths"][path])
    assert "Idempotency-Key" in str(schema["paths"]["/api/v1/patients"]["post"])


def test_lifecycle_outbox_has_no_unexpected_dead_letter(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    with postgres_session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(OutboxEventRecord)
                .where(OutboxEventRecord.status == OutboxStatus.DEAD_LETTER.value)
            )
            == 0
        )


def test_deterministic_seed_is_repeatable_and_uses_lifecycle_handlers(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    seed_main()
    seed_main()
    case_ids = [uuid5(SEED_NAMESPACE, f"case:{name}") for name, *_ in CASES]
    with postgres_session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(ClinicalCaseRecord)
            .where(ClinicalCaseRecord.id.in_(case_ids))
        ) == len(CASES)
        assert (
            session.scalar(
                select(func.count())
                .select_from(CommandIdempotencyRecord)
                .where(CommandIdempotencyRecord.actor_id == ACTOR_ID)
            )
            == len(CASES) * 3
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(TimelineEventRecord)
                .where(TimelineEventRecord.case_id.in_(case_ids))
            )
            == len(CASES) * 3
        )
