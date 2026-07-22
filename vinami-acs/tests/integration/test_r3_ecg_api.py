"""PostgreSQL-backed acceptance tests for the R3 ECG Intelligence slice."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from vinami.ecg.adapters.ingestion import build_demo_waveform
from vinami.ecg.adapters.r3_persistence import (
    ECGAIAnalysisRecord,
    ECGStudyDetailRecord,
    PhysicianECGInterpretationRecord,
)
from vinami.shared.config import Settings

NOW = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)


def _settings(artifact_root: Path) -> Settings:
    return Settings(
        database_url=os.environ["VINAMI_DATABASE_URL"],
        identity_mode="development",
        ecg_artifact_root=artifact_root,
        ecg_allow_mock_provider=True,
    )


def _headers(key: str | None = None, identity: str = "physician") -> dict[str, str]:
    headers = {
        "X-Development-Identity": identity,
        "X-Correlation-ID": str(uuid4()),
        "X-Request-Source": "pytest-r3",
    }
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _case(client: TestClient) -> dict[str, object]:
    suffix = str(uuid4())
    patient = client.post(
        "/api/v1/patients",
        headers=_headers(f"r3-patient-{suffix}", "nurse"),
        json={"patient_reference": f"R3-SYN-{suffix}", "safe_demographic_summary": {}},
    )
    assert patient.status_code == 201, patient.text
    encounter = client.post(
        "/api/v1/encounters",
        headers=_headers(f"r3-encounter-{suffix}", "nurse"),
        json={
            "patient_id": patient.json()["patient_id"],
            "location": "Synthetic ECG laboratory",
            "arrival_at": NOW.isoformat(),
        },
    )
    assert encounter.status_code == 201, encounter.text
    clinical_case = client.post(
        "/api/v1/clinical-cases",
        headers=_headers(f"r3-case-{suffix}"),
        json={
            "encounter_id": encounter.json()["encounter_id"],
            "opening_reason": "Synthetic R3 ECG acceptance",
            "priority": "urgent",
        },
    )
    assert clinical_case.status_code == 201, clinical_case.text
    return clinical_case.json()


def _upload(
    client: TestClient,
    case_id: str,
    case_version: int,
    reference: str,
    key: str,
    acquisition_at: datetime = NOW,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/clinical-cases/{case_id}/ecg-studies",
        headers=_headers(key, "nurse"),
        data={
            "source_type": "canonical_waveform",
            "study_reference": reference,
            "acquisition_at": acquisition_at.isoformat(),
            "content_type": "application/vnd.vinami.ecg+json",
            "expected_case_version": str(case_version),
        },
        files={
            "artifact": (
                f"{reference}.json",
                build_demo_waveform(),
                "application/vnd.vinami.ecg+json",
            )
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "completed"
    return response.json()


def test_r3_ecg_vertical_slice_is_persisted_versioned_and_audited(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    with TestClient(create_app(_settings(tmp_path / "ecg-artifacts"))) as client:
        clinical_case = _case(client)
        case_id = str(clinical_case["case_id"])
        case_version = int(clinical_case["aggregate_version"])

        first_job = _upload(
            client, case_id, case_version, f"R3-ECG-{uuid4()}", f"r3-upload-{uuid4()}"
        )
        first_study_id = str(first_job["resulting_study_id"])
        quality = client.get(f"/api/v1/ecg-studies/{first_study_id}/quality", headers=_headers())
        assert quality.status_code == 200
        assert quality.json()["status"] == "acceptable"
        assert quality.json()["suppress_score_emphasis"] is False

        analysis_key = f"r3-analysis-{uuid4()}"
        analysis = client.post(
            f"/api/v1/ecg-studies/{first_study_id}/analyses",
            headers=_headers(analysis_key),
            json={"provider_name": "mock"},
        )
        repeated_analysis = client.post(
            f"/api/v1/ecg-studies/{first_study_id}/analyses",
            headers={**_headers(identity="physician"), "Idempotency-Key": analysis_key},
            json={"provider_name": "mock"},
        )
        assert analysis.status_code == 201, analysis.text
        assert repeated_analysis.status_code == 201, repeated_analysis.text
        assert repeated_analysis.json()["analysis_id"] == analysis.json()["analysis_id"]
        findings = analysis.json()["findings"]
        assert len(findings) == 5
        assert [item["rank"] for item in findings] == [1, 2, 3, 4, 5]
        assert [item["model_score"] for item in findings] == sorted(
            (item["model_score"] for item in findings), reverse=True
        )
        assert {item["finding_code"] for item in findings} == {"NORM", "MI", "STTC", "CD", "HYP"}
        assert (
            next(item for item in findings if item["finding_code"] == "MI")["display_label"]
            == "MI-related ECG pattern"
        )
        assert analysis.json()["synthetic"] is True
        assert analysis.json()["safety_notice"] == "Model scores are not clinical probabilities."

        interpretation = client.post(
            f"/api/v1/ecg-studies/{first_study_id}/physician-interpretations",
            headers=_headers(f"r3-interpretation-{uuid4()}"),
            json={
                "analysis_id": analysis.json()["analysis_id"],
                "interpretation_status": "reviewed",
                "structured_interpretation": "Synthetic physician review entry.",
                "agreement_status": "requires_clinical_correlation",
                "quality_disposition": "acceptable_for_review",
                "repeat_ecg_requested": True,
                "occurred_at": (NOW + timedelta(minutes=3)).isoformat(),
                "expected_version": 0,
            },
        )
        assert interpretation.status_code == 201, interpretation.text
        assert interpretation.json()["revision_number"] == 1

        second_job = _upload(
            client,
            case_id,
            case_version,
            f"R3-ECG-{uuid4()}",
            f"r3-second-upload-{uuid4()}",
            NOW + timedelta(minutes=10),
        )
        second_study_id = str(second_job["resulting_study_id"])
        comparison = client.post(
            f"/api/v1/clinical-cases/{case_id}/ecg-comparisons",
            headers=_headers(f"r3-comparison-{uuid4()}"),
            json={
                "baseline_study_id": first_study_id,
                "current_study_id": second_study_id,
            },
        )
        assert comparison.status_code == 201, comparison.text
        assert comparison.json()["comparability_status"] == "comparable"
        assert len(comparison.json()["lead_comparisons"]) == 12
        assert comparison.json()["comparison_policy_version"].startswith("r18-dynamic-ecg")
        assert comparison.json()["signal_feature_deltas"]
        assert comparison.json()["review_recommendation"].startswith("Dynamic ECG comparison")
        assert "physician interpretation required" in comparison.json()["safety_notice"]

        reminder = client.post(
            f"/api/v1/clinical-cases/{case_id}/repeat-ecg-reminders",
            headers=_headers(f"r3-reminder-{uuid4()}"),
            json={
                "source_study_id": first_study_id,
                "reason": "Synthetic serial ECG review",
                "due_at": (NOW + timedelta(minutes=30)).isoformat(),
            },
        )
        assert reminder.status_code == 201, reminder.text
        acknowledged = client.post(
            f"/api/v1/repeat-ecg-reminders/{reminder.json()['reminder_id']}/acknowledge",
            headers=_headers(f"r3-reminder-ack-{uuid4()}", "nurse"),
            json={"expected_version": 1},
        )
        assert acknowledged.status_code == 200, acknowledged.text
        assert acknowledged.json()["status"] == "acknowledged"

        workspace = client.get(
            f"/api/v1/clinical-cases/{case_id}/ecg-workspace", headers=_headers()
        )
        assert workspace.status_code == 200, workspace.text
        assert len(workspace.json()["studies"]) == 2
        assert workspace.json()["current_study"]["study_id"] == second_study_id
        assert workspace.json()["safety_notice"] == "Model scores are not clinical probabilities."

        dispatch = client.app.state.container.event_dispatcher().dispatch_pending(limit=200)
        assert dispatch.dead_lettered == 0
        timeline = client.get(
            f"/api/v1/clinical-cases/{case_id}/timeline", headers=_headers()
        ).json()
        audit = client.get(
            f"/api/v1/clinical-cases/{case_id}/audit", headers=_headers(identity="auditor")
        ).json()

    expected_events = {
        "ECGStudyCreated.v1",
        "ECGQualityAssessed.v1",
        "ECGAnalysisCompleted.v1",
        "PhysicianECGInterpretationRecorded.v1",
        "DynamicECGComparisonCompleted.v1",
        "RepeatECGReminderScheduled.v1",
        "RepeatECGReminderAcknowledged.v1",
    }
    assert expected_events <= {item["event_type"] for item in timeline}
    assert {f"event:{event}" for event in expected_events} <= {item["action"] for item in audit}

    with postgres_session_factory() as session:
        case_uuid = UUID(case_id)
        assert (
            session.scalar(
                select(func.count())
                .select_from(ECGStudyDetailRecord)
                .where(ECGStudyDetailRecord.clinical_case_id == case_uuid)
            )
            == 2
        )
        assert session.scalar(select(func.count()).select_from(ECGAIAnalysisRecord)) >= 1
        assert (
            session.scalar(select(func.count()).select_from(PhysicianECGInterpretationRecord)) >= 1
        )


def test_r3_ecg_rejects_unsafe_upload_and_non_physician_interpretation(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "ecg-artifacts-errors"))) as client:
        clinical_case = _case(client)
        case_id = str(clinical_case["case_id"])
        version = int(clinical_case["aggregate_version"])
        malformed = client.post(
            f"/api/v1/clinical-cases/{case_id}/ecg-studies",
            headers=_headers(f"r3-malformed-{uuid4()}", "nurse"),
            data={
                "source_type": "canonical_waveform",
                "study_reference": f"R3-BAD-{uuid4()}",
                "acquisition_at": NOW.isoformat(),
                "content_type": "application/vnd.vinami.ecg+json",
                "expected_case_version": str(version),
            },
            files={
                "artifact": (
                    "bad.json",
                    b"not-json",
                    "application/vnd.vinami.ecg+json",
                )
            },
        )
        assert malformed.status_code == 415

        job = _upload(client, case_id, version, f"R3-ECG-{uuid4()}", f"r3-safe-{uuid4()}")
        forbidden = client.post(
            f"/api/v1/ecg-studies/{job['resulting_study_id']}/physician-interpretations",
            headers=_headers(f"r3-forbidden-{uuid4()}", "nurse"),
            json={
                "interpretation_status": "reviewed",
                "structured_interpretation": "Synthetic entry",
                "agreement_status": "not_assessed",
                "quality_disposition": "acceptable_for_review",
                "occurred_at": NOW.isoformat(),
                "expected_version": 0,
            },
        )
        assert forbidden.status_code == 403


def test_openapi_exposes_r3_ecg_contracts(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "ecg-artifacts-openapi"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/v1/clinical-cases/{case_id}/ecg-studies": {"get", "post"},
        "/api/v1/ecg-studies/{study_id}/quality": {"get"},
        "/api/v1/ecg-studies/{study_id}/analyses": {"get", "post"},
        "/api/v1/ecg-studies/{study_id}/physician-interpretations": {"get", "post"},
        "/api/v1/clinical-cases/{case_id}/ecg-comparisons": {"get", "post"},
        "/api/v1/clinical-cases/{case_id}/repeat-ecg-reminders": {"get", "post"},
        "/api/v1/clinical-cases/{case_id}/ecg-workspace": {"get"},
        "/api/v1/model-registry/ecg": {"get"},
    }
    assert all(methods <= set(paths[path]) for path, methods in expected.items())
