"""R10 real-time and simulated hospital integration acceptance coverage."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.test_r3_ecg_api import NOW, _case, _headers, _settings
from tests.integration.test_r7_command_center_api import _make_visible


def _lab_payload(
    case: dict[str, object], external_id: str, value: str = "12.4"
) -> dict[str, object]:
    return {
        "external_message_id": external_id,
        "source_system": "simulated-lis-r10",
        "schema_version": "vinami-hl7-lab-result.v1",
        "clinical_case_id": case["case_id"],
        "assay_code": "DEMO-HS-CTNI-01",
        "analyte": "cardiac_troponin_i",
        "value": value,
        "unit": "ng/L",
        "specimen_type": "plasma",
        "specimen_collected_at": NOW.isoformat(),
        "resulted_at": (NOW + timedelta(minutes=2)).isoformat(),
        "result_status": "final",
        "source_result_id": external_id,
        "expected_case_version": case["aggregate_version"],
    }


def _dispatch_all(client: TestClient) -> None:
    dispatcher = client.app.state.container.event_dispatcher()
    for _ in range(10):
        summary = dispatcher.dispatch_pending(limit=500)
        if summary.published == 0:
            break


def test_r10_simulated_lab_duplicate_amendment_and_realtime_snapshot(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "r10-lab"))) as client:
        case = _case(client)
        _make_visible(case, postgres_session_factory, "Emergency Department")
        case_id = str(case["case_id"])
        external_id = f"R10-LAB-{uuid4()}"

        created = client.post(
            "/api/v1/integration/simulated/laboratory-results",
            headers=_headers(f"r10-lab-{uuid4()}", "physician"),
            json=_lab_payload(case, external_id),
        )
        assert created.status_code == 201, created.text
        message = created.json()
        assert message["status"] == "processed"
        assert message["simulated"] is True
        assert len(message["linked_record_ids"]) == 1

        duplicate = client.post(
            "/api/v1/integration/simulated/laboratory-results",
            headers=_headers(f"r10-lab-dup-{uuid4()}", "physician"),
            json=_lab_payload(case, external_id),
        )
        assert duplicate.status_code == 201, duplicate.text
        assert duplicate.json()["message_id"] == message["message_id"]
        assert duplicate.json()["linked_record_ids"] == message["linked_record_ids"]

        amendment = client.post(
            "/api/v1/integration/simulated/laboratory-results",
            headers=_headers(f"r10-lab-amend-{uuid4()}", "physician"),
            json={
                **_lab_payload(case, f"{external_id}-AMEND", "14.1"),
                "amendment_of_message_id": external_id,
                "amendment_reason": "Corrected simulated LIS result.",
            },
        )
        assert amendment.status_code == 201, amendment.text
        assert amendment.json()["status"] == "processed"

        workspace = client.get(
            f"/api/v1/clinical-cases/{case_id}/troponin-workspace",
            headers=_headers(identity="physician"),
        )
        assert workspace.status_code == 200
        history = workspace.json()["result_history"]
        assert len(history) == 2
        assert history[1]["supersedes_result_id"] == history[0]["result_id"]

        _dispatch_all(client)
        realtime = client.get(
            "/api/v1/realtime/events/snapshot",
            headers=_headers(identity="physician"),
            params={"case_id": case_id},
        )
        assert realtime.status_code == 200, realtime.text
        event_types = {item["event_type"] for item in realtime.json()}
        assert "IntegrationMessageProcessed.v1" in event_types
        assert "TroponinResultAmended.v1" in event_types
        last_id = realtime.json()[0]["event_id"]
        resumed = client.get(
            "/api/v1/realtime/events/snapshot",
            headers=_headers(identity="physician"),
            params={"case_id": case_id, "last_event_id": last_id},
        )
        assert resumed.status_code == 200

        timeline = client.get(
            f"/api/v1/clinical-cases/{case_id}/history/timeline",
            headers=_headers(identity="physician"),
            params={"event_type": "IntegrationMessageProcessed.v1"},
        )
        assert timeline.status_code == 200
        assert timeline.json()["total"] >= 1


def test_r10_simulated_ecg_invalid_message_and_retry_status(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    _ = postgres_session_factory
    with TestClient(create_app(_settings(tmp_path / "r10-ecg"))) as client:
        case = _case(client)
        _make_visible(case, postgres_session_factory, "Emergency Department")
        case_id = str(case["case_id"])

        ecg = client.post(
            "/api/v1/integration/simulated/ecg-studies",
            headers=_headers(f"r10-ecg-{uuid4()}", "physician"),
            json={
                "external_message_id": f"R10-ECG-{uuid4()}",
                "source_system": "simulated-ecg-device-r10",
                "schema_version": "vinami-ecg-device-study.v1",
                "clinical_case_id": case_id,
                "study_reference": f"R10-ECG-{uuid4()}",
                "acquisition_at": NOW.isoformat(),
                "expected_case_version": case["aggregate_version"],
            },
        )
        assert ecg.status_code == 201, ecg.text
        assert ecg.json()["status"] == "processed"
        assert len(ecg.json()["linked_record_ids"]) == 2

        invalid = client.post(
            "/api/v1/integration/simulated/laboratory-results",
            headers=_headers(f"r10-invalid-{uuid4()}", "physician"),
            json={**_lab_payload(case, f"R10-BAD-{uuid4()}"), "unit": "mg/dL"},
        )
        assert invalid.status_code == 201, invalid.text
        assert invalid.json()["status"] in {"failed", "dead_letter"}
        assert invalid.json()["validation_errors"]

        temporary = client.post(
            "/api/v1/integration/simulated/laboratory-results",
            headers=_headers(f"r10-temp-{uuid4()}", "physician"),
            json={**_lab_payload(case, f"R10-TEMP-{uuid4()}", "13.2"), "failure_mode": "temporary"},
        )
        assert temporary.status_code == 201, temporary.text
        assert temporary.json()["status"] == "retry_pending"

        retried = client.post(
            f"/api/v1/integration/messages/{temporary.json()['message_id']}/retry",
            headers=_headers(f"r10-retry-{uuid4()}", "physician"),
            json={"expected_version": temporary.json()["record_version"]},
        )
        assert retried.status_code == 200, retried.text
        assert retried.json()["status"] == "processed"

        messages = client.get(
            "/api/v1/integration/messages", headers=_headers(identity="physician")
        )
        assert messages.status_code == 200
        assert any(item["status"] == "failed" for item in messages.json())
