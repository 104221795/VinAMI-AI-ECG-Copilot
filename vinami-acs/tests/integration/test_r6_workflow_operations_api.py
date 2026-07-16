"""PostgreSQL-backed R6 workflow, task, alert, and safety acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.test_r3_ecg_api import _case, _headers, _settings

from vinami.alerts.adapters.persistence import AlertRecord, AlertTransitionRecord
from vinami.audit.adapters.persistence import AuditLogRecord, OutboxEventRecord
from vinami.identity.adapters.development import DEVELOPMENT_IDENTITIES
from vinami.timeline.adapters.persistence import TimelineEventRecord
from vinami.workflow.adapters.persistence import (
    ClinicalTaskRecord,
    ClinicalTaskTransitionRecord,
)


def _physician_decision(
    client: TestClient, case: dict[str, object], decision_type: str
) -> dict[str, object]:
    case_id = str(case["case_id"])
    snapshot = client.post(
        f"/api/v1/clinical-cases/{case_id}/clinical-reasoning/snapshots",
        headers=_headers(f"r6-snapshot-{uuid4()}", "physician"),
        json={"expected_case_version": int(case["aggregate_version"])},
    ).json()
    assessment = client.post(
        f"/api/v1/clinical-cases/{case_id}/clinical-reasoning/assessments",
        headers=_headers(f"r6-assessment-{uuid4()}", "physician"),
        json={
            "snapshot_id": snapshot["snapshot_id"],
            "expected_snapshot_version": 1,
            "summary": "Physician-authored assessment for operational follow-up.",
            "supporting_evidence": ["clinical_case:v1"],
            "contradictory_evidence": [],
            "uncertainty": "Further human review remains required.",
        },
    ).json()
    response = client.post(
        f"/api/v1/clinical-cases/{case_id}/clinical-reasoning/decisions",
        headers=_headers(f"r6-decision-{uuid4()}", "physician"),
        json={
            "snapshot_id": snapshot["snapshot_id"],
            "assessment_id": assessment["assessment_id"],
            "expected_snapshot_version": 1,
            "expected_assessment_version": 1,
            "decision_type": decision_type,
            "rationale": "Physician documented an operational review request.",
            "uncertainty": "The request is not a diagnosis or treatment instruction.",
            "evidence_references": ["clinical_case:v1"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _generate_task(
    client: TestClient,
    case_id: str,
    decision: dict[str, object],
    due_at: datetime | None = None,
) -> object:
    workspace = client.get(
        f"/api/v1/clinical-cases/{case_id}/workflow-operations",
        headers=_headers(identity="physician"),
    ).json()
    return client.post(
        f"/api/v1/clinical-cases/{case_id}/workflow-operations/tasks/from-decisions",
        headers=_headers(f"r6-task-{uuid4()}", "physician"),
        json={
            "decision_id": decision["decision_id"],
            "expected_decision_version": decision["record_version"],
            "expected_workflow_version": workspace["workflow"]["version"],
            "priority": "urgent",
            "due_at": due_at.isoformat() if due_at else None,
        },
    )


def test_r6_standard_task_lifecycle_persists_history_events_and_audit(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r6-standard"))
    with TestClient(app) as client:
        case = _case(client)
        case_id = str(case["case_id"])
        decision = _physician_decision(client, case, "request_repeat_ecg")
        generated = _generate_task(client, case_id, decision)
        assert generated.status_code == 201, generated.text
        task = generated.json()
        assert task["status"] == "pending"

        physician_id = str(DEVELOPMENT_IDENTITIES["physician"].actor_id)
        for action, body in (
            ("assign", {"owner_user_id": physician_id}),
            ("acknowledge", {}),
            ("start", {}),
            ("complete", {"reason": "Repeat ECG work documented as complete."}),
        ):
            response = client.post(
                f"/api/v1/clinical-cases/{case_id}/workflow-operations/tasks/{task['task_id']}/{action}",
                headers=_headers(f"r6-{action}-{uuid4()}", "physician"),
                json={"expected_version": task["version"], **body},
            )
            assert response.status_code == 200, response.text
            task = response.json()
        assert task["status"] == "completed"
        assert len(task["history"]) == 4

        stale = client.post(
            f"/api/v1/clinical-cases/{case_id}/workflow-operations/tasks/{task['task_id']}/cancel",
            headers=_headers(f"r6-stale-{uuid4()}", "physician"),
            json={"expected_version": 1, "reason": "Stale request"},
        )
        assert stale.status_code == 409

        reloaded = client.get(
            f"/api/v1/clinical-cases/{case_id}/workflow-operations",
            headers=_headers(identity="physician"),
        )
        assert reloaded.status_code == 200
        assert reloaded.json()["tasks"][0]["status"] == "completed"

        dispatcher = app.state.container.event_dispatcher()
        for _ in range(10):
            summary = dispatcher.dispatch_pending(limit=100)
            if summary.published + summary.retried + summary.dead_lettered + summary.skipped == 0:
                break
        with postgres_session_factory() as session:
            task_id = UUID(task["task_id"])
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ClinicalTaskTransitionRecord)
                    .where(ClinicalTaskTransitionRecord.task_id == task_id)
                )
                == 4
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEventRecord)
                    .where(OutboxEventRecord.aggregate_id == task_id)
                )
                >= 5
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(TimelineEventRecord)
                    .where(
                        TimelineEventRecord.case_id == UUID(case_id),
                        TimelineEventRecord.event_type == "ClinicalTaskTransitioned.v1",
                    )
                )
                == 4
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AuditLogRecord)
                    .where(
                        AuditLogRecord.case_id == UUID(case_id),
                        AuditLogRecord.action == "event:ClinicalTaskTransitioned.v1",
                    )
                )
                == 4
            )


def test_r6_overdue_alert_deduplication_revocation_and_cath_guard(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r6-safety"))
    with TestClient(app) as client:
        case = _case(client)
        case_id = str(case["case_id"])
        decision = _physician_decision(client, case, "request_repeat_troponin")
        generated = _generate_task(
            client, case_id, decision, datetime.now(UTC) - timedelta(minutes=2)
        )
        assert generated.status_code == 201, generated.text
        task_id = generated.json()["task_id"]

        for index in range(2):
            evaluated = client.post(
                f"/api/v1/clinical-cases/{case_id}/workflow-operations/overdue-evaluations",
                headers=_headers(f"r6-overdue-{index}-{uuid4()}", "physician"),
                json={},
            )
            assert evaluated.status_code == 200, evaluated.text
        workspace = client.get(
            f"/api/v1/clinical-cases/{case_id}/workflow-operations",
            headers=_headers(identity="physician"),
        ).json()
        assert workspace["tasks"][0]["status"] == "overdue"
        assert workspace["tasks"][0]["escalation_level"] == 1
        assert len([a for a in workspace["alerts"] if a["task_id"] == task_id]) == 1

        alert = workspace["alerts"][0]
        acknowledged = client.post(
            f"/api/v1/clinical-cases/{case_id}/workflow-operations/alerts/{alert['alert_id']}/acknowledge",
            headers=_headers(f"r6-alert-{uuid4()}", "nurse"),
            json={"expected_version": alert["version"]},
        )
        assert acknowledged.status_code == 200

        missing_authority = client.post(
            f"/api/v1/clinical-cases/{case_id}/workflow-operations/tasks/from-decisions",
            headers=_headers(f"r6-fake-{uuid4()}", "physician"),
            json={
                "decision_id": str(uuid4()),
                "expected_decision_version": 1,
                "expected_workflow_version": workspace["workflow"]["version"],
                "priority": "routine",
            },
        )
        assert missing_authority.status_code == 404

        cath = _physician_decision(client, case, "request_cath_lab_review")
        cath_task = _generate_task(client, case_id, cath)
        assert cath_task.status_code == 201, cath_task.text
        revoked = client.post(
            f"/api/v1/clinical-cases/{case_id}/clinical-reasoning/decisions/{cath['decision_id']}/revocations",
            headers=_headers(f"r6-revoke-{uuid4()}", "physician"),
            json={
                "snapshot_id": cath["snapshot_id"],
                "assessment_id": cath["assessment_id"],
                "expected_snapshot_version": 1,
                "expected_assessment_version": 1,
                "expected_decision_version": 1,
                "decision_type": "request_cath_lab_review",
                "rationale": "Physician withdrew the review request.",
                "uncertainty": "No new task is authorized.",
                "evidence_references": ["clinical_case:v1"],
                "revocation_reason": "Clinical plan revised by physician.",
                "operation": "revoke",
            },
        )
        assert revoked.status_code == 201, revoked.text
        blocked = _generate_task(client, case_id, cath)
        assert blocked.status_code == 409

        with postgres_session_factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AlertRecord)
                    .where(AlertRecord.task_id == UUID(task_id))
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(AlertTransitionRecord)
                    .where(AlertTransitionRecord.alert_id == UUID(alert["alert_id"]))
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ClinicalTaskRecord)
                    .where(ClinicalTaskRecord.case_id == UUID(case_id))
                )
                == 2
            )
