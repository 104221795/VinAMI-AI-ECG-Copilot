"""PostgreSQL-backed R7 Command Center projection acceptance tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from apps.api.app import create_app
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker
from tests.integration.test_r3_ecg_api import _case, _headers, _settings
from tests.integration.test_r6_workflow_operations_api import (
    _generate_task,
    _physician_decision,
)

from vinami.identity.adapters.development import DEVELOPMENT_IDENTITIES
from vinami.patient.adapters.persistence import EncounterRecord


def _make_visible(
    case: dict[str, object], session_factory: sessionmaker[Session], location: str
) -> None:
    with session_factory() as session:
        encounter = session.get(EncounterRecord, UUID(str(case["encounter_id"])))
        assert encounter is not None
        encounter.location = location
        session.commit()


def test_r7_aggregates_authoritative_operational_state_and_filters(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r7-aggregation"))
    with TestClient(app) as client:
        visible = _case(client)
        hidden = _case(client)
        _make_visible(visible, postgres_session_factory, "Emergency Department")
        _make_visible(hidden, postgres_session_factory, "Outside physician scope")
        case_id = str(visible["case_id"])

        effective = _physician_decision(client, visible, "request_repeat_troponin")
        task_response = _generate_task(
            client,
            case_id,
            effective,
            datetime.now(UTC) - timedelta(minutes=5),
        )
        assert task_response.status_code == 201, task_response.text
        evaluated = client.post(
            f"/api/v1/clinical-cases/{case_id}/workflow-operations/overdue-evaluations",
            headers=_headers(f"r7-overdue-{uuid4()}", "physician"),
            json={},
        )
        assert evaluated.status_code == 200, evaluated.text

        revoked_source = _physician_decision(client, visible, "request_repeat_ecg")
        revoked = client.post(
            f"/api/v1/clinical-cases/{case_id}/clinical-reasoning/decisions/"
            f"{revoked_source['decision_id']}/revocations",
            headers=_headers(f"r7-revoke-{uuid4()}", "physician"),
            json={
                "snapshot_id": revoked_source["snapshot_id"],
                "assessment_id": revoked_source["assessment_id"],
                "expected_snapshot_version": 1,
                "expected_assessment_version": 1,
                "expected_decision_version": 1,
                "decision_type": "request_repeat_ecg",
                "rationale": "Physician withdrew the repeat ECG request.",
                "uncertainty": "No operational authority remains from this record.",
                "evidence_references": ["clinical_case:v1"],
                "revocation_reason": "Physician plan changed.",
                "operation": "revoke",
            },
        )
        assert revoked.status_code == 201, revoked.text

        response = client.get(
            "/api/v1/command-center/cases",
            headers=_headers(identity="physician"),
            params={
                "priority": "critical",
                "workflow_state": "NEW",
                "overdue": "true",
                "alert_status": "unresolved",
                "evidence_status": "missing",
                "sort": "priority",
                "direction": "desc",
                "page": 1,
                "page_size": 1,
            },
        )
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["total"] == 1
        assert len(page["items"]) == 1
        item = page["items"][0]
        assert item["case_id"] == case_id
        assert item["workflow_state"] == "NEW"
        assert item["active_task_count"] == 1
        assert item["overdue_task_count"] == 1
        assert item["unresolved_alert_count"] == 1
        assert item["operational_priority"] == "critical"
        assert item["priority_reason"] in {
            "Unresolved urgent operational alert",
            "Persisted R6 escalation",
        }
        assert item["decision_id"] == effective["decision_id"]
        assert item["decision_id"] != revoked_source["decision_id"]
        assert item["evidence_status"] == "missing"
        assert {"triage", "vitals", "ecg", "troponin"}.issubset(item["missing_evidence"])
        assert item["tasks"][0]["status"] == "overdue"
        assert item["alerts"][0]["status"] == "active"
        assert item["next_due_at"] is not None
        assert item["oldest_overdue_at"] is not None
        assert item["update_token"]

        unauthorized = client.get(
            "/api/v1/command-center/cases",
            headers={"X-Development-Identity": "unknown"},
        )
        assert unauthorized.status_code == 401


def test_r7_query_count_is_constant_and_r6_updates_replace_counts(
    postgres_session_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    app = create_app(_settings(tmp_path / "r7-efficiency"))
    with TestClient(app) as client:
        case = _case(client)
        _make_visible(case, postgres_session_factory, "Emergency Department")
        case_id = str(case["case_id"])
        decision = _physician_decision(client, case, "request_repeat_ecg")
        task = _generate_task(client, case_id, decision).json()

        statements: list[str] = []

        def capture(_connection: object, _cursor: object, statement: str, *args: object) -> None:
            if "r7_" in statement:
                statements.append(statement)

        event.listen(app.state.container.database.engine, "before_cursor_execute", capture)
        try:
            initial = client.get(
                "/api/v1/command-center/cases",
                headers=_headers(identity="physician"),
                params={"sort": "opened_at", "direction": "asc", "page_size": 25},
            )
        finally:
            event.remove(app.state.container.database.engine, "before_cursor_execute", capture)
        assert initial.status_code == 200, initial.text
        assert len(statements) <= 4
        initial_item = next(item for item in initial.json()["items"] if item["case_id"] == case_id)
        assert initial_item["active_task_count"] == 1

        for action, extra in (
            (
                "assign",
                {"owner_user_id": str(DEVELOPMENT_IDENTITIES["physician"].actor_id)},
            ),
            ("acknowledge", {}),
            ("start", {}),
            ("complete", {"reason": "Operational work completed by the physician."}),
        ):
            changed = client.post(
                f"/api/v1/clinical-cases/{case_id}/workflow-operations/tasks/"
                f"{task['task_id']}/{action}",
                headers=_headers(f"r7-{action}-{uuid4()}", "physician"),
                json={"expected_version": task["version"], **extra},
            )
            assert changed.status_code == 200, changed.text
            task = changed.json()
        refreshed = client.get(
            "/api/v1/command-center/cases",
            headers=_headers(identity="physician"),
        )
        assert refreshed.status_code == 200, refreshed.text
        item = next(item for item in refreshed.json()["items"] if item["case_id"] == case_id)
        assert item["active_task_count"] == 0
        assert item["tasks"] == []
        assert item["update_token"] != initial_item["update_token"]
