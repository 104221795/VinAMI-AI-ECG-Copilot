"""R9 Timeline, Audit, Outcome and Learning acceptance tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.test_r3_ecg_api import NOW, _case, _headers, _settings
from tests.integration.test_r7_command_center_api import _make_visible
from tests.integration.test_r8_complete_case_workspace_api import _populate_case


def _outcome_payload(
    conclusion: str = "Physician-documented disposition outcome.",
) -> dict[str, object]:
    return {
        "outcome_type": "disposition",
        "outcome_timestamp": NOW.isoformat(),
        "final_conclusion": conclusion,
        "disposition": "observation_completed",
        "destination": "cardiology_follow_up",
        "data_completeness": "documented",
        "source": "physician_documented",
        "uncertainty": "Research-use MVP documentation only.",
        "unavailable_reason": None,
    }


def _dispatch_all(app: object) -> int:
    dispatcher = app.state.container.event_dispatcher()
    published = 0
    for _ in range(20):
        summary = dispatcher.dispatch_pending(limit=500)
        published += summary.published
        if summary.published == 0:
            break
    return published


def test_r9_outcome_revision_timeline_audit_and_model_provenance(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r9-history"))
    with TestClient(app) as client:
        case = _case(client)
        _make_visible(case, postgres_session_factory, "Emergency Department")
        _populate_case(client, case)
        case_id = str(case["case_id"])

        unauthorized = client.post(
            f"/api/v1/clinical-cases/{case_id}/outcomes",
            headers=_headers(f"r9-nurse-{uuid4()}", "nurse"),
            json=_outcome_payload("Nurse should not record this."),
        )
        assert unauthorized.status_code == 403

        key = f"r9-outcome-{uuid4()}"
        created = client.post(
            f"/api/v1/clinical-cases/{case_id}/outcomes",
            headers=_headers(key, "physician"),
            json=_outcome_payload(),
        )
        assert created.status_code == 201, created.text
        first = created.json()
        assert first["revision_number"] == 1
        assert first["final_conclusion"] == "Physician-documented disposition outcome."

        duplicate = client.post(
            f"/api/v1/clinical-cases/{case_id}/outcomes",
            headers=_headers(key, "physician"),
            json=_outcome_payload(),
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["outcome_id"] == first["outcome_id"]

        second_initial = client.post(
            f"/api/v1/clinical-cases/{case_id}/outcomes",
            headers=_headers(f"r9-outcome-second-{uuid4()}", "physician"),
            json=_outcome_payload("Do not overwrite initial outcome."),
        )
        assert second_initial.status_code == 409

        corrected = client.post(
            f"/api/v1/clinical-cases/{case_id}/outcomes/{first['outcome_id']}/corrections",
            headers=_headers(f"r9-correct-{uuid4()}", "physician"),
            json={
                **_outcome_payload("Corrected physician-documented outcome."),
                "correction_reason": "Clarified destination after chart review.",
            },
        )
        assert corrected.status_code == 201, corrected.text
        assert corrected.json()["revision_number"] == 2
        assert corrected.json()["supersedes_outcome_id"] == first["outcome_id"]

        assert _dispatch_all(app) >= 2

        outcomes = client.get(
            f"/api/v1/clinical-cases/{case_id}/outcomes",
            headers=_headers(identity="physician"),
        )
        assert outcomes.status_code == 200
        outcome_history = outcomes.json()
        assert (
            outcome_history["current"]["final_conclusion"]
            == "Corrected physician-documented outcome."
        )
        assert len(outcome_history["revisions"]) == 2

        timeline = client.get(
            f"/api/v1/clinical-cases/{case_id}/history/timeline",
            headers=_headers(identity="physician"),
            params={"correction_status": "correction"},
        )
        assert timeline.status_code == 200, timeline.text
        assert any(
            item["event_type"] == "ClinicalOutcomeCorrected.v1" for item in timeline.json()["items"]
        )
        assert timeline.json()["items"][0]["source_record_version"] == 1

        audit = client.get(
            f"/api/v1/clinical-cases/{case_id}/history/audit",
            headers=_headers(identity="physician"),
            params={"outcome": "success", "page_size": 100},
        )
        assert audit.status_code == 200, audit.text
        outcome_audits = [
            item for item in audit.json()["items"] if item["resource_type"] == "ClinicalOutcome"
        ]
        assert {item["correction_status"] for item in outcome_audits} >= {"original", "correction"}
        assert all(item["authorization_result"] == "authorized" for item in outcome_audits)

        provenance = client.get(
            f"/api/v1/clinical-cases/{case_id}/model-provenance",
            headers=_headers(identity="physician"),
        )
        assert provenance.status_code == 200, provenance.text
        assert provenance.json()[0]["synthetic"] is True
        assert "not diagnoses" in provenance.json()[0]["safety_notice"]


def test_r9_research_export_pseudonymizes_identifiers_and_records_checksum(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r9-export"))
    with TestClient(app) as client:
        case = _case(client)
        _make_visible(case, postgres_session_factory, "Emergency Department")
        case_id = str(case["case_id"])
        outcome = client.post(
            f"/api/v1/clinical-cases/{case_id}/outcomes",
            headers=_headers(f"r9-export-outcome-{uuid4()}", "physician"),
            json=_outcome_payload("Outcome included in research export."),
        )
        assert outcome.status_code == 201, outcome.text

        export = client.post(
            "/api/v1/research-exports",
            headers=_headers(f"r9-export-{uuid4()}", "physician"),
            json={"case_ids": [case_id]},
        )
        assert export.status_code == 201, export.text
        value = export.json()
        assert value["status"] == "completed"
        assert value["schema_version"] == "vinami.research_export.r9.v1"
        assert value["row_count"] == 1
        assert len(value["checksum_sha256"]) == 64
        assert "R3-SYN-" not in str(value["content_json"])
        assert "research_case_id" in value["content_csv"]
        assert value["content_json"]["cases"][0]["outcomes"][0]["final_conclusion"] == (
            "Outcome included in research export."
        )

        fetched = client.get(
            f"/api/v1/research-exports/{value['export_id']}",
            headers=_headers(identity="physician"),
        )
        assert fetched.status_code == 200
        assert fetched.json()["checksum_sha256"] == value["checksum_sha256"]
