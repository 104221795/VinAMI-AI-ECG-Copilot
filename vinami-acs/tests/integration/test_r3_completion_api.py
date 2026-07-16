"""PostgreSQL-backed R3 completion tests for hospital ingestion and serial workflow."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.test_r3_ecg_api import NOW, _case, _headers, _settings, _upload

from vinami.ecg.adapters.ingestion import build_demo_dicom, build_demo_xml


def _file_upload(
    client: TestClient,
    case_id: str,
    source_type: str,
    content_type: str,
    content: bytes,
    suffix: str,
) -> dict[str, object]:
    reference = f"R3-{source_type.upper()}-{uuid4()}"
    response = client.post(
        f"/api/v1/clinical-cases/{case_id}/ecg-studies",
        headers=_headers(f"r3-format-{uuid4()}", "technician"),
        data={
            "source_type": source_type,
            "study_reference": reference,
            "acquisition_at": NOW.isoformat(),
            "content_type": content_type,
        },
        files={"artifact": (f"{reference}.{suffix}", content, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_hospital_formats_pdf_document_only_and_connector_retry(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "r3-completion-formats"))) as client:
        case_id = str(_case(client)["case_id"])

        dicom = _file_upload(
            client, case_id, "dicom_file", "application/dicom", build_demo_dicom(), "dcm"
        )
        dicom_study = client.get(
            f"/api/v1/ecg-studies/{dicom['resulting_study_id']}", headers=_headers()
        ).json()
        assert dicom_study["waveform_available"] is True
        assert dicom_study["sampling_rate_hz"] == 100
        assert dicom_study["source_format"] == "dicom-waveform"

        xml = _file_upload(
            client, case_id, "vendor_xml", "application/xml", build_demo_xml(), "xml"
        )
        xml_study = client.get(
            f"/api/v1/ecg-studies/{xml['resulting_study_id']}", headers=_headers()
        ).json()
        assert xml_study["source_format"] == "vinami-canonical-xml-v1"
        assert xml_study["waveform_available"] is True

        pdf = _file_upload(
            client,
            case_id,
            "pdf_document",
            "application/pdf",
            b"%PDF-1.4\n%%EOF",
            "pdf",
        )
        pdf_study_id = str(pdf["resulting_study_id"])
        pdf_study = client.get(f"/api/v1/ecg-studies/{pdf_study_id}", headers=_headers()).json()
        assert pdf_study["waveform_available"] is False
        assert pdf_study["lead_configuration"] == "document-only"
        waveform = client.get(f"/api/v1/ecg-studies/{pdf_study_id}/waveform", headers=_headers())
        assert waveform.status_code == 409
        preview = client.get(f"/api/v1/ecg-studies/{pdf_study_id}/preview", headers=_headers())
        assert preview.status_code == 200 and preview.headers["content-type"] == "application/pdf"

        failed = client.post(
            f"/api/v1/clinical-cases/{case_id}/ecg-imports",
            headers=_headers(f"r3-connector-fail-{uuid4()}", "technician"),
            json={
                "source_type": "dicom_connector",
                "source_connector_id": "mock-dicom-source",
                "external_reference": "R3-DICOM-RETRY",
                "study_reference": f"R3-RETRY-{uuid4()}",
                "acquisition_at": NOW.isoformat(),
            },
        )
        assert failed.status_code == 504
        jobs = client.get(
            f"/api/v1/clinical-cases/{case_id}/ecg-imports", headers=_headers()
        ).json()
        failed_job = next(item for item in jobs if item["external_reference"] == "R3-DICOM-RETRY")
        assert failed_job["status"] == "failed"
        assert (
            failed_job["failure_detail_safe"] == "mock hospital ECG retrieval requires a safe retry"
        )
        retry = client.post(
            f"/api/v1/ecg-ingestion-jobs/{failed_job['ingestion_job_id']}/retry",
            headers=_headers(f"r3-connector-retry-{uuid4()}", "technician"),
            json={"expected_version": failed_job["record_version"]},
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["status"] == "completed"
        assert retry.json()["retry_count"] == 1
        assert (
            len(
                [
                    item
                    for item in client.get(
                        f"/api/v1/clinical-cases/{case_id}/ecg-imports", headers=_headers()
                    ).json()
                    if item["external_reference"] == "R3-DICOM-RETRY"
                ]
            )
            == 1
        )


def test_dynamic_review_score_evolution_and_repeat_reminder_lifecycle(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "r3-completion-dynamic"))) as client:
        case = _case(client)
        case_id = str(case["case_id"])
        version = int(case["aggregate_version"])
        baseline = _upload(
            client, case_id, version, f"R3-BASE-{uuid4()}", f"r3-base-{uuid4()}", NOW
        )
        current = _upload(
            client,
            case_id,
            version,
            f"R3-CURRENT-{uuid4()}",
            f"r3-current-{uuid4()}",
            NOW + timedelta(minutes=12),
        )
        for job in (baseline, current):
            response = client.post(
                f"/api/v1/ecg-studies/{job['resulting_study_id']}/analyses",
                headers=_headers(f"r3-evolution-analysis-{uuid4()}"),
                json={"provider_name": "mock"},
            )
            assert response.status_code == 201, response.text

        comparison = client.post(
            f"/api/v1/clinical-cases/{case_id}/ecg-comparisons",
            headers=_headers(f"r3-dynamic-{uuid4()}"),
            json={
                "baseline_study_id": baseline["resulting_study_id"],
                "current_study_id": current["resulting_study_id"],
            },
        )
        assert comparison.status_code == 201, comparison.text
        comparison_value = comparison.json()
        assert comparison_value["comparability_status"] == "comparable"
        assert comparison_value["model_score_compatibility"] == "compatible"
        assert len(comparison_value["model_score_deltas"]) == 5
        assert all(
            item["compatibility_status"] == "compatible"
            for item in comparison_value["model_score_deltas"]
        )

        review = client.post(
            f"/api/v1/ecg-comparisons/{comparison_value['comparison_id']}/physician-reviews",
            headers=_headers(f"r3-dynamic-review-{uuid4()}"),
            json={
                "review_status": "technical_change_acknowledged",
                "interpretation": (
                    "Synthetic technical comparison reviewed; clinical correlation required."
                ),
                "occurred_at": (NOW + timedelta(minutes=15)).isoformat(),
                "expected_version": 0,
            },
        )
        assert review.status_code == 201, review.text
        assert review.json()["revision_number"] == 1

        reminder = client.post(
            f"/api/v1/clinical-cases/{case_id}/repeat-ecg-reminders",
            headers=_headers(f"r3-repeat-{uuid4()}"),
            json={
                "source_study_id": baseline["resulting_study_id"],
                "reason": "Physician requested repeat technical ECG",
                "due_at": (NOW + timedelta(minutes=20)).isoformat(),
                "origin": "physician_request",
            },
        )
        assert reminder.status_code == 201, reminder.text
        reminder_id = reminder.json()["reminder_id"]
        acknowledged = client.post(
            f"/api/v1/repeat-ecg-reminders/{reminder_id}/acknowledge",
            headers=_headers(f"r3-repeat-ack-{uuid4()}", "nurse"),
            json={"expected_version": 1},
        )
        assert acknowledged.status_code == 200, acknowledged.text
        completed = client.post(
            f"/api/v1/repeat-ecg-reminders/{reminder_id}/complete",
            headers=_headers(f"r3-repeat-complete-{uuid4()}", "nurse"),
            json={
                "expected_version": acknowledged.json()["record_version"],
                "completed_study_id": current["resulting_study_id"],
            },
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"
        assert completed.json()["completed_at"] is not None

        workspace = client.get(
            f"/api/v1/clinical-cases/{case_id}/ecg-workspace", headers=_headers()
        ).json()
        assert workspace["capabilities"]["dynamic_ecg"] is True
        assert len(workspace["ingestion_jobs"]) == 2
        assert len(workspace["comparison_reviews"]) == 1
        assert workspace["reminders"][0]["status"] == "completed"

        summary = client.app.state.container.event_dispatcher().dispatch_pending(limit=300)
        assert summary.dead_lettered == 0
        timeline = client.get(
            f"/api/v1/clinical-cases/{case_id}/timeline", headers=_headers()
        ).json()
        event_types = {item["event_type"] for item in timeline}
        assert "DynamicECGPhysicianReviewRecorded.v1" in event_types
        assert "RepeatECGReminderCompleted.v1" in event_types
