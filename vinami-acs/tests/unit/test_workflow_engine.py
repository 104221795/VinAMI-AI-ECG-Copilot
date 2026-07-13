"""Workflow tests covering observational facts and authoritative clinical decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from vinami.shared.domain import DomainInvariantError, OptimisticConcurrencyError
from vinami.workflow.application.definitions import load_demo_workflow_definition
from vinami.workflow.domain.decision import (
    PhysicianDecision,
    PhysicianDecisionStatus,
    PhysicianDecisionType,
)
from vinami.workflow.domain.definition import WorkflowCommand, WorkflowState
from vinami.workflow.domain.model import ClinicalWorkflow

NOW = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)
ACTOR_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_VERSION = 2


def _workflow() -> ClinicalWorkflow:
    return ClinicalWorkflow.start(uuid4(), load_demo_workflow_definition())


def _decision(
    workflow: ClinicalWorkflow,
    decision_type: PhysicianDecisionType,
    *,
    actor_id: UUID = ACTOR_ID,
    actor_role: str = "physician",
    status: PhysicianDecisionStatus = PhysicianDecisionStatus.ACTIVE,
) -> PhysicianDecision:
    return PhysicianDecision(
        decision_id=uuid4(),
        clinical_case_id=workflow.case_id,
        actor_id=actor_id,
        actor_role=actor_role,
        decision_type=decision_type,
        decision_status=status,
        reason_code="demo-review",
        note=None,
        evidence_snapshot_reference="evidence://snapshot/1",
        workflow_version=workflow.version,
        aggregate_expected_version=CASE_VERSION,
        occurred_at=NOW,
        recorded_at=NOW,
        correlation_id=uuid4(),
        causation_id=None,
        corrects_decision_id=uuid4() if status is PhysicianDecisionStatus.REVOKED else None,
    )


def _execute(
    workflow: ClinicalWorkflow,
    command_type: str,
    facts: dict[str, bool | int] | None = None,
    due_at: datetime | None = None,
    command_id: UUID | None = None,
    decision_type: PhysicianDecisionType | None = None,
) -> None:
    decision = _decision(workflow, decision_type) if decision_type is not None else None
    command = WorkflowCommand(
        command_type=command_type,
        expected_version=workflow.version,
        facts_patch=facts or {},
        actor_id=decision.actor_id if decision else None,
        actor_role=decision.actor_role if decision else None,
        decision_id=decision.decision_id if decision else None,
        case_expected_version=CASE_VERSION if decision else None,
        correlation_id=decision.correlation_id if decision else uuid4(),
        due_at=due_at,
        issued_at=NOW,
        command_id=command_id if command_id is not None else uuid4(),
    )
    workflow.execute(load_demo_workflow_definition(), command, decision=decision)


def _to_awaiting_troponin(workflow: ClinicalWorkflow) -> None:
    _execute(workflow, "start_triage")
    _execute(workflow, "complete_triage")
    _execute(workflow, "record_ecg", {"ecg_available": True, "ecg_quality_acceptable": True})
    _execute(workflow, "request_troponin", due_at=NOW + timedelta(minutes=30))


def _to_pathway_selected(workflow: ClinicalWorkflow) -> None:
    _to_awaiting_troponin(workflow)
    _execute(workflow, "record_troponin", {"troponin_available": True})
    _execute(workflow, "select_demo_pathway")
    _execute(
        workflow,
        "record_physician_decision",
        decision_type=PhysicianDecisionType.PATHWAY_ACCEPTED,
    )


def test_normal_demo_closure_route_requires_distinct_authoritative_decisions() -> None:
    """The workflow cannot close from ECG/troponin facts or one reusable boolean."""
    workflow = _workflow()
    _to_pathway_selected(workflow)
    _execute(
        workflow,
        "prepare_discharge_review",
        decision_type=PhysicianDecisionType.DISCHARGE_REVIEW_APPROVED,
    )
    _execute(
        workflow,
        "close_case",
        {"unresolved_critical_alerts": 0},
        decision_type=PhysicianDecisionType.CASE_CLOSURE_APPROVED,
    )

    assert workflow.state is WorkflowState.CLOSED
    assert workflow.physician_decision_id is not None
    assert workflow.facts.troponin_available


def test_rising_troponin_path_creates_review_alert_and_repeat_ecg_task() -> None:
    workflow = _workflow()
    _to_awaiting_troponin(workflow)
    _execute(workflow, "record_troponin", {"troponin_available": True, "troponin_rising": True})

    assert workflow.state is WorkflowState.PHYSICIAN_REVIEW_REQUIRED
    assert {task.task_type for task in workflow.generated_tasks} >= {
        "physician_review",
        "repeat_ecg",
    }
    assert workflow.generated_alerts[0].alert_type == "rising_troponin_requires_review"


def test_repeat_ecg_overdue_creates_a_review_alert() -> None:
    workflow = _workflow()
    _to_awaiting_troponin(workflow)
    _execute(
        workflow,
        "record_troponin",
        {"troponin_available": True, "troponin_rising": True},
        due_at=NOW + timedelta(minutes=15),
    )
    _execute(workflow, "repeat_ecg_due", {"repeat_ecg_overdue": True})

    assert workflow.generated_alerts[-1].alert_type == "repeat_ecg_overdue_requires_review"


def test_poor_ecg_quality_blocks_normal_ai_interpretation() -> None:
    workflow = _workflow()
    _execute(workflow, "start_triage")
    _execute(workflow, "complete_triage")
    _execute(workflow, "record_ecg", {"ecg_available": True, "ecg_quality_acceptable": False})

    assert workflow.state is WorkflowState.PHYSICIAN_REVIEW_REQUIRED
    assert workflow.generated_alerts[-1].alert_type == "poor_ecg_quality_requires_review"


def test_conflicting_ai_and_clinician_signals_require_review() -> None:
    workflow = _workflow()
    _to_awaiting_troponin(workflow)
    _execute(
        workflow,
        "record_troponin",
        {"troponin_available": True, "conflicting_signals": True},
    )
    assert workflow.state is WorkflowState.PHYSICIAN_REVIEW_REQUIRED


def test_transfer_requires_a_current_transfer_decision() -> None:
    workflow = _workflow()
    _to_pathway_selected(workflow)
    _execute(
        workflow,
        "request_transfer",
        decision_type=PhysicianDecisionType.TRANSFER_REVIEW_REQUESTED,
    )
    assert workflow.state is WorkflowState.TRANSFER_IN_PROGRESS


def test_duplicate_observational_command_is_a_no_op() -> None:
    workflow = _workflow()
    command_id = uuid4()
    command = WorkflowCommand(
        "start_triage", workflow.version, command_id=command_id, issued_at=NOW
    )
    first = workflow.execute(load_demo_workflow_definition(), command)
    duplicate = workflow.execute(load_demo_workflow_definition(), command)
    assert not first.duplicate
    assert duplicate.duplicate
    assert workflow.version == 2


def test_stale_aggregate_version_is_rejected() -> None:
    workflow = _workflow()
    _execute(workflow, "start_triage")
    with pytest.raises(OptimisticConcurrencyError):
        workflow.execute(
            load_demo_workflow_definition(),
            WorkflowCommand("complete_triage", 1, issued_at=NOW),
        )


def test_authoritative_fact_patch_is_always_rejected() -> None:
    with pytest.raises(DomainInvariantError, match="authoritative workflow state"):
        WorkflowCommand(
            "record_troponin",
            1,
            facts_patch={"physician_decision_recorded": True},
            issued_at=NOW,
        )


def test_ai_only_cath_lab_review_bypass_is_rejected() -> None:
    workflow = _workflow()
    _to_pathway_selected(workflow)
    command = WorkflowCommand(
        "request_cath_lab_review",
        workflow.version,
        actor_id=ACTOR_ID,
        actor_role="physician",
        decision_id=uuid4(),
        case_expected_version=CASE_VERSION,
        issued_at=NOW,
    )
    with pytest.raises(DomainInvariantError, match="persisted physician decision"):
        workflow.execute(load_demo_workflow_definition(), command, decision=None)


def test_cath_lab_review_rejects_wrong_decision_type_and_revoked_decision() -> None:
    workflow = _workflow()
    _to_pathway_selected(workflow)
    wrong = _decision(workflow, PhysicianDecisionType.PATHWAY_ACCEPTED)
    command = WorkflowCommand(
        "request_cath_lab_review",
        workflow.version,
        actor_id=wrong.actor_id,
        actor_role=wrong.actor_role,
        decision_id=wrong.decision_id,
        case_expected_version=CASE_VERSION,
        issued_at=NOW,
    )
    with pytest.raises(DomainInvariantError, match="decision type"):
        workflow.execute(load_demo_workflow_definition(), command, decision=wrong)

    revoked = _decision(
        workflow,
        PhysicianDecisionType.CATH_LAB_REVIEW_REQUESTED,
        status=PhysicianDecisionStatus.REVOKED,
    )
    revoked_command = WorkflowCommand(
        "request_cath_lab_review",
        workflow.version,
        actor_id=revoked.actor_id,
        actor_role=revoked.actor_role,
        decision_id=revoked.decision_id,
        case_expected_version=CASE_VERSION,
        issued_at=NOW,
    )
    with pytest.raises(DomainInvariantError, match="revoked"):
        workflow.execute(load_demo_workflow_definition(), revoked_command, decision=revoked)
