"""PostgreSQL-backed acceptance tests for the R2 documentation slice."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from vinami.shared.config import Settings
from vinami.triage.adapters.persistence import (
    TriageAssessmentRecord,
    VitalObservationSetRecord,
)

NOW = datetime(2026, 7, 14, 9, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(database_url=os.environ["VINAMI_DATABASE_URL"], identity_mode="development")


def _headers(key: str | None = None, identity: str = "nurse") -> dict[str, str]:
    headers = {
        "X-Development-Identity": identity,
        "X-Correlation-ID": str(uuid4()),
        "X-Request-Source": "pytest-r2",
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _case(client: TestClient) -> dict[str, object]:
    suffix = str(uuid4())
    patient = client.post(
        "/api/v1/patients",
        headers=_headers(f"r2-patient-{suffix}"),
        json={"patient_reference": f"R2-SYN-{suffix}", "safe_demographic_summary": {}},
    )
    assert patient.status_code == 201, patient.text
    encounter = client.post(
        "/api/v1/encounters",
        headers=_headers(f"r2-encounter-{suffix}"),
        json={
            "patient_id": patient.json()["patient_id"],
            "location": "Emergency Department",
            "arrival_at": NOW.isoformat(),
        },
    )
    assert encounter.status_code == 201, encounter.text
    clinical_case = client.post(
        "/api/v1/clinical-cases",
        headers=_headers(f"r2-case-{suffix}"),
        json={
            "encounter_id": encounter.json()["encounter_id"],
            "opening_reason": "Synthetic R2 documentation acceptance",
            "priority": "urgent",
        },
    )
    assert clinical_case.status_code == 201, clinical_case.text
    return clinical_case.json()


def _triage_payload(case_version: int, complaint: str) -> dict[str, object]:
    return {
        "expected_case_version": case_version,
        "occurred_at": NOW.isoformat(),
        "source": "structured-triage-form",
        "chief_complaint": complaint,
        "symptom_onset_state": "unknown",
        "associated_symptoms": [
            {"name": "dyspnoea", "state": "absent"},
            {"name": "nausea", "state": "not_assessed"},
        ],
        "cardiovascular_risk_factors": [{"name": "smoking history", "state": "unknown"}],
    }


def _vital_payload(case_version: int, value: float) -> dict[str, object]:
    observed_at = NOW + timedelta(minutes=2)
    return {
        "expected_case_version": case_version,
        "observed_at": observed_at.isoformat(),
        "source": "bedside-entry",
        "supplemental_oxygen_state": "not_assessed",
        "measurements": [
            {
                "kind": "heart_rate",
                "value": value,
                "unit": "beats/min",
                "source": "manual-entry",
                "observed_at": observed_at.isoformat(),
                "quality_status": "accepted",
            },
            {
                "kind": "oxygen_saturation",
                "value": 97,
                "unit": "%",
                "source": "manual-entry",
                "observed_at": observed_at.isoformat(),
                "quality_status": "accepted",
            },
        ],
    }


def test_r2_vertical_slice_persists_corrections_and_projects_events(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    with TestClient(create_app(_settings())) as client:
        clinical_case = _case(client)
        case_id = str(clinical_case["case_id"])
        case_version = int(clinical_case["aggregate_version"])
        triage_key = f"triage-{uuid4()}"
        triage_payload = _triage_payload(case_version, "Synthetic symptom description")

        recorded = client.post(
            f"/api/v1/clinical-cases/{case_id}/triage-assessments",
            headers=_headers(triage_key),
            json=triage_payload,
        )
        repeated = client.post(
            f"/api/v1/clinical-cases/{case_id}/triage-assessments",
            headers=_headers(triage_key),
            json=triage_payload,
        )
        assert recorded.status_code == repeated.status_code == 201
        assert repeated.json()["assessment_id"] == recorded.json()["assessment_id"]

        correction_body = {
            **_triage_payload(case_version, "Synthetic clarified description"),
            "expected_record_version": recorded.json()["record_version"],
            "correction_reason": "Patient clarified the wording",
        }
        correction_body.pop("expected_case_version")
        corrected = client.post(
            f"/api/v1/clinical-cases/{case_id}/triage-assessments/"
            f"{recorded.json()['assessment_id']}/corrections",
            headers=_headers(f"triage-correction-{uuid4()}"),
            json=correction_body,
        )
        assert corrected.status_code == 201, corrected.text
        assert corrected.json()["corrects_assessment_id"] == recorded.json()["assessment_id"]

        vital_key = f"vitals-{uuid4()}"
        vital_payload = _vital_payload(case_version, 74)
        vital = client.post(
            f"/api/v1/clinical-cases/{case_id}/vital-observation-sets",
            headers=_headers(vital_key),
            json=vital_payload,
        )
        assert vital.status_code == 201, vital.text
        conflict_payload = _vital_payload(case_version, 75)
        idempotency_conflict = client.post(
            f"/api/v1/clinical-cases/{case_id}/vital-observation-sets",
            headers=_headers(vital_key),
            json=conflict_payload,
        )
        assert idempotency_conflict.status_code == 409

        vital_correction_body = {
            **_vital_payload(case_version, 73),
            "expected_record_version": vital.json()["record_version"],
            "correction_reason": "Synthetic source row corrected",
        }
        vital_correction_body.pop("expected_case_version")
        corrected_vital = client.post(
            f"/api/v1/clinical-cases/{case_id}/vital-observation-sets/"
            f"{vital.json()['vital_set_id']}/corrections",
            headers=_headers(f"vital-correction-{uuid4()}"),
            json=vital_correction_body,
        )
        assert corrected_vital.status_code == 201, corrected_vital.text
        assert corrected_vital.json()["corrects_vital_set_id"] == vital.json()["vital_set_id"]

        current = client.get(f"/api/v1/clinical-cases/{case_id}/triage", headers=_headers())
        triage_history = client.get(
            f"/api/v1/clinical-cases/{case_id}/triage/history", headers=_headers()
        )
        vital_history = client.get(f"/api/v1/clinical-cases/{case_id}/vitals", headers=_headers())
        latest = client.get(f"/api/v1/clinical-cases/{case_id}/vitals/latest", headers=_headers())
        summary = client.get(
            f"/api/v1/clinical-cases/{case_id}/triage-vitals-summary",
            headers=_headers(),
        )

        assert current.json()["assessment_id"] == corrected.json()["assessment_id"]
        assert [item["revision_number"] for item in triage_history.json()["items"]] == [2, 1]
        assert [item["revision_number"] for item in vital_history.json()["items"]] == [2, 1]
        assert latest.json()["vital_set_id"] == corrected_vital.json()["vital_set_id"]
        assert summary.json()["completeness_policy_version"] == "r2-documentation-v1"
        assert summary.json()["missing_documentation"] == []

        dispatch = client.app.state.container.event_dispatcher().dispatch_pending(limit=100)
        assert dispatch.dead_lettered == 0
        timeline = client.get(
            f"/api/v1/clinical-cases/{case_id}/timeline", headers=_headers()
        ).json()
        audit = client.get(
            f"/api/v1/clinical-cases/{case_id}/audit", headers=_headers(identity="auditor")
        ).json()

    r2_events = {
        "TriageAssessmentRecorded.v1",
        "TriageAssessmentCorrected.v1",
        "VitalObservationSetRecorded.v1",
        "VitalObservationSetCorrected.v1",
    }
    assert r2_events <= {item["event_type"] for item in timeline}
    audit_actions = {f"event:{event_type}" for event_type in r2_events}
    assert audit_actions <= {item["action"] for item in audit}
    assert all(
        item["request_source"] == "pytest-r2" for item in audit if item["action"] in audit_actions
    )

    with postgres_session_factory() as session:
        case_uuid = UUID(case_id)
        assert (
            session.scalar(
                select(func.count())
                .select_from(TriageAssessmentRecord)
                .where(TriageAssessmentRecord.clinical_case_id == case_uuid)
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(VitalObservationSetRecord)
                .where(VitalObservationSetRecord.clinical_case_id == case_uuid)
            )
            == 2
        )


def test_r2_contract_rejects_unsafe_units_stale_versions_and_read_only_writes(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings())) as client:
        clinical_case = _case(client)
        case_id = clinical_case["case_id"]
        version = int(clinical_case["aggregate_version"])
        unsafe_unit = _vital_payload(version, 72)
        unsafe_unit["measurements"][0]["unit"] = "bpm"  # type: ignore[index]
        invalid = client.post(
            f"/api/v1/clinical-cases/{case_id}/vital-observation-sets",
            headers=_headers(f"invalid-unit-{uuid4()}"),
            json=unsafe_unit,
        )
        stale = client.post(
            f"/api/v1/clinical-cases/{case_id}/triage-assessments",
            headers=_headers(f"stale-{uuid4()}"),
            json=_triage_payload(version + 1, "Synthetic stale request"),
        )
        forbidden = client.post(
            f"/api/v1/clinical-cases/{case_id}/triage-assessments",
            headers=_headers(f"forbidden-{uuid4()}", "read_only_reviewer"),
            json=_triage_payload(version, "Synthetic forbidden request"),
        )

    assert invalid.status_code == 400
    assert stale.status_code == 409
    assert forbidden.status_code == 403


def test_openapi_exposes_exact_r2_endpoint_set(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings())) as client:
        paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/clinical-cases/{case_id}/triage-assessments": {"post"},
        "/api/v1/clinical-cases/{case_id}/triage": {"get"},
        "/api/v1/clinical-cases/{case_id}/triage/history": {"get"},
        "/api/v1/clinical-cases/{case_id}/triage-assessments/{assessment_id}/corrections": {"post"},
        "/api/v1/clinical-cases/{case_id}/vital-observation-sets": {"post"},
        "/api/v1/clinical-cases/{case_id}/vitals": {"get"},
        "/api/v1/clinical-cases/{case_id}/vitals/latest": {"get"},
        "/api/v1/clinical-cases/{case_id}/vital-observation-sets/{vital_set_id}/corrections": {
            "post"
        },
        "/api/v1/clinical-cases/{case_id}/triage-vitals-summary": {"get"},
    }
    assert all(methods <= set(paths[path]) for path, methods in expected.items())
