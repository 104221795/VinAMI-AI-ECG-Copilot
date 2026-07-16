"""Focused R7 evidence-freshness projection tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from vinami.clinical_case.adapters.command_center import SQLAlchemyCommandCenterReadRepository
from vinami.clinical_case.domain.model import CaseStatus, ClinicalPriority
from vinami.clinical_case.ports.command_center import CommandCenterQuery
from vinami.workflow.domain.definition import WorkflowState


def _row(now: datetime) -> dict[str, object]:
    return {
        "case_id": uuid4(),
        "encounter_id": uuid4(),
        "patient_id": uuid4(),
        "patient_reference": "R7-UNIT",
        "age_band": None,
        "sex_at_birth": None,
        "location": "Emergency Department",
        "case_status": CaseStatus.OPEN,
        "case_priority": ClinicalPriority.URGENT,
        "case_version": 1,
        "opened_at": now - timedelta(hours=1),
        "workflow_id": uuid4(),
        "workflow_state": WorkflowState.NEW,
        "workflow_version": 1,
        "operational_priority": "urgent",
        "priority_reason": "Human-recorded urgent case priority",
        "active_task_count": 0,
        "overdue_task_count": 0,
        "unresolved_alert_count": 0,
        "next_due_at": None,
        "oldest_overdue_at": None,
        "owner_user_id": None,
        "owner_team_id": None,
        "snapshot_id": uuid4(),
        "snapshot_created_at": now,
        "freshness": {},
        "missing_evidence": [],
        "technical_conflicts": [],
        "evidence_status": "current",
        "decision_id": None,
        "decision_type": None,
        "decision_rationale": None,
        "decision_recorded_at": None,
        "latest_activity_at": now,
        "max_task_version": 0,
        "max_alert_version": 0,
        "triage_at": now,
        "vitals_at": now,
        "ecg_at": now,
        "troponin_at": now,
        "ecg_quality_status": "acceptable",
    }


def _query(now: datetime) -> CommandCenterQuery:
    return CommandCenterQuery(
        1, 25, None, None, None, None, None, None, "priority", "desc", (), now
    )


def test_r7_evidence_freshness_distinguishes_current_stale_and_technical_limit() -> None:
    now = datetime(2026, 7, 16, 1, 0, tzinfo=UTC)
    current_view = SQLAlchemyCommandCenterReadRepository._map(_row(now), [], [], _query(now))
    assert set(current_view.evidence_freshness.values()) == {"current"}
    assert current_view.missing_evidence == ()

    stale = _row(now)
    stale["troponin_at"] = now - timedelta(hours=25)
    stale["evidence_status"] = "stale"
    stale_view = SQLAlchemyCommandCenterReadRepository._map(stale, [], [], _query(now))
    assert stale_view.evidence_freshness["troponin"] == "stale"
    assert stale_view.evidence_status == "stale"

    limited = _row(now)
    limited["ecg_quality_status"] = "limited"
    limited["evidence_status"] = "technical_limit"
    limited_view = SQLAlchemyCommandCenterReadRepository._map(limited, [], [], _query(now))
    assert limited_view.evidence_freshness["ecg"] == "technical_limit"
    assert limited_view.technical_limits == ("Latest ECG quality is limited",)
