"""PostgreSQL-backed R8 complete case-workspace acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.test_r2_triage_vitals_api import (
    _triage_payload,
    _vital_payload,
)
from tests.integration.test_r3_ecg_api import NOW, _case, _headers, _settings, _upload
from tests.integration.test_r4_1_troponin_api import _record
from tests.integration.test_r6_workflow_operations_api import (
    _generate_task,
    _physician_decision,
)
from tests.integration.test_r7_command_center_api import _make_visible

from vinami.identity.adapters.development import DEVELOPMENT_IDENTITIES
from vinami.timeline.adapters.persistence import TimelineEventRecord


def _populate_case(
    client: TestClient,
    case: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    case_id = str(case["case_id"])
    case_version = int(case["aggregate_version"])
    triage = client.post(
        f"/api/v1/clinical-cases/{case_id}/triage-assessments",
        headers=_headers(f"r8-triage-{uuid4()}", "nurse"),
        json=_triage_payload(case_version, "Synthetic R8 chest discomfort"),
    )
    assert triage.status_code == 201, triage.text
    vitals = client.post(
        f"/api/v1/clinical-cases/{case_id}/vital-observation-sets",
        headers=_headers(f"r8-vitals-{uuid4()}", "nurse"),
        json=_vital_payload(case_version, 82),
    )
    assert vitals.status_code == 201, vitals.text

    ingestion = _upload(
        client,
        case_id,
        case_version,
        f"R8-ECG-{uuid4()}",
        f"r8-upload-{uuid4()}",
    )
    study_id = str(ingestion["resulting_study_id"])
    analysis = client.post(
        f"/api/v1/ecg-studies/{study_id}/analyses",
        headers=_headers(f"r8-analysis-{uuid4()}"),
        json={"provider_name": "mock"},
    )
    assert analysis.status_code == 201, analysis.text
    interpretation = client.post(
        f"/api/v1/ecg-studies/{study_id}/physician-interpretations",
        headers=_headers(f"r8-interpretation-{uuid4()}"),
        json={
            "analysis_id": analysis.json()["analysis_id"],
            "interpretation_status": "reviewed",
            "structured_interpretation": "Physician-authored R8 ECG interpretation.",
            "agreement_status": "requires_clinical_correlation",
            "quality_disposition": "acceptable_for_review",
            "repeat_ecg_requested": False,
            "occurred_at": (NOW + timedelta(minutes=3)).isoformat(),
            "expected_version": 0,
        },
    )
    assert interpretation.status_code == 201, interpretation.text
    _record(client, case_id, case_version, minute=10, source=f"r8-first-{uuid4()}")
    _record(client, case_id, case_version, minute=25, source=f"r8-second-{uuid4()}")
    decision = _physician_decision(client, case, "request_repeat_troponin")
    task = _generate_task(client, case_id, decision).json()
    return decision, task


def _timeline_rows(session_factory: sessionmaker[Session], case_id: UUID) -> tuple[UUID, UUID]:
    older, newer = uuid4(), uuid4()
    with session_factory() as session:
        session.add_all(
            [
                TimelineEventRecord(
                    id=older,
                    case_id=case_id,
                    event_type="R8Older.v1",
                    title="Older R8 activity",
                    occurred_at=datetime.now(UTC) - timedelta(minutes=2),
                    recorded_at=datetime.now(UTC),
                    source="r8-test",
                    actor_id=None,
                    correlation_id=uuid4(),
                    causation_id=None,
                    payload={},
                    source_event_id=uuid4(),
                ),
                TimelineEventRecord(
                    id=newer,
                    case_id=case_id,
                    event_type="R8Newer.v1",
                    title="Newer R8 activity",
                    occurred_at=datetime.now(UTC) - timedelta(minutes=1),
                    recorded_at=datetime.now(UTC),
                    source="r8-test",
                    actor_id=None,
                    correlation_id=uuid4(),
                    causation_id=None,
                    payload={},
                    source_event_id=uuid4(),
                ),
            ]
        )
        session.commit()
    return older, newer


def test_r8_aggregates_complete_effective_case_state_and_orders_timeline(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r8-complete"))
    with TestClient(app) as client:
        case = _case(client)
        _make_visible(case, postgres_session_factory, "Emergency Department")
        decision, _ = _populate_case(client, case)
        _, newer = _timeline_rows(postgres_session_factory, UUID(str(case["case_id"])))

        response = client.get(
            f"/api/v1/clinical-cases/{case['case_id']}/complete-workspace",
            headers=_headers(identity="physician"),
        )
        assert response.status_code == 200, response.text
        workspace = response.json()
        assert workspace["patient_reference"].startswith("R3-SYN-")
        assert workspace["triage"]["chief_complaint"] == "Synthetic R8 chest discomfort"
        assert workspace["vitals"]["measurements"]
        assert workspace["ecg"]["quality_status"] == "acceptable"
        assert workspace["ecg"]["analysis"]["status"] == "completed"
        assert (
            "Physician-authored"
            in workspace["ecg"]["physician_interpretation"]["structured_interpretation"]
        )
        assert workspace["troponin"]["result_count"] == 2
        assert workspace["troponin"]["latest_delta"]["compatibility_status"] == "compatible"
        assert workspace["evidence_snapshot"]["sources"]
        assert workspace["physician_assessment"] is not None
        assert workspace["physician_decision"]["decision_id"] == decision["decision_id"]
        assert workspace["workflow"]["state"] == "NEW"
        assert len(workspace["tasks"]) == 1
        assert workspace["timeline"][0]["timeline_event_id"] == str(newer)
        assert workspace["update_token"]


def test_r8_visibility_revocation_update_token_and_query_count(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r8-safety"))
    with TestClient(app) as client:
        case = _case(client)
        _make_visible(case, postgres_session_factory, "Emergency Department")
        effective, task = _populate_case(client, case)
        revoked_source = _physician_decision(client, case, "request_repeat_ecg")
        revoked = client.post(
            f"/api/v1/clinical-cases/{case['case_id']}/clinical-reasoning/decisions/"
            f"{revoked_source['decision_id']}/revocations",
            headers=_headers(f"r8-revoke-{uuid4()}"),
            json={
                "snapshot_id": revoked_source["snapshot_id"],
                "assessment_id": revoked_source["assessment_id"],
                "expected_snapshot_version": 1,
                "expected_assessment_version": 1,
                "expected_decision_version": 1,
                "decision_type": "request_repeat_ecg",
                "rationale": "Physician withdrew the R8 request.",
                "uncertainty": "No authority remains from the revoked record.",
                "evidence_references": ["clinical_case:v1"],
                "revocation_reason": "Physician plan changed.",
                "operation": "revoke",
            },
        )
        assert revoked.status_code == 201, revoked.text

        selects: list[str] = []

        def capture(_connection: object, _cursor: object, statement: str, *args: object) -> None:
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        event.listen(app.state.container.database.engine, "before_cursor_execute", capture)
        try:
            initial = client.get(
                f"/api/v1/clinical-cases/{case['case_id']}/complete-workspace",
                headers=_headers(identity="physician"),
            )
        finally:
            event.remove(app.state.container.database.engine, "before_cursor_execute", capture)
        assert initial.status_code == 200, initial.text
        value = initial.json()
        assert value["physician_decision"]["decision_id"] == effective["decision_id"]
        assert value["physician_decision"]["decision_id"] != revoked_source["decision_id"]
        assert len(selects) <= 20

        for action, extra in (
            (
                "assign",
                {"owner_user_id": str(DEVELOPMENT_IDENTITIES["physician"].actor_id)},
            ),
            ("acknowledge", {}),
            ("start", {}),
            ("complete", {"reason": "R8 owning workspace completed the task."}),
        ):
            completed = client.post(
                f"/api/v1/clinical-cases/{case['case_id']}/workflow-operations/tasks/"
                f"{task['task_id']}/{action}",
                headers=_headers(f"r8-{action}-{uuid4()}"),
                json={"expected_version": task["version"], **extra},
            )
            assert completed.status_code == 200, completed.text
            task = completed.json()
        refreshed = client.get(
            f"/api/v1/clinical-cases/{case['case_id']}/complete-workspace",
            headers=_headers(identity="physician"),
        ).json()
        assert refreshed["tasks"] == []
        assert refreshed["update_token"] != value["update_token"]

        _make_visible(case, postgres_session_factory, "Outside physician scope")
        hidden = client.get(
            f"/api/v1/clinical-cases/{case['case_id']}/complete-workspace",
            headers=_headers(identity="physician"),
        )
        assert hidden.status_code == 404
