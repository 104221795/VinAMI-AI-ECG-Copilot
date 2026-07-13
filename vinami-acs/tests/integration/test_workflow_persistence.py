"""PostgreSQL tests for workflow state, effect persistence, timers, and idempotency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from vinami.alerts.adapters.persistence import AlertRecord
from vinami.clinical_case.domain.model import ClinicalCase, ClinicalPriority
from vinami.patient.domain.model import (
    Demographics,
    Encounter,
    Patient,
    PatientIdentifier,
    PersonName,
)
from vinami.shared.unit_of_work import SQLAlchemyUnitOfWork
from vinami.workflow.adapters.persistence import (
    ClinicalTaskRecord,
    ClinicalWorkflowRecord,
    WorkflowCommandReceiptRecord,
    WorkflowDueTimerRecord,
)
from vinami.workflow.application.commands import WorkflowCommandHandler, WorkflowTimerService
from vinami.workflow.application.definitions import load_demo_workflow_definition
from vinami.workflow.domain.definition import DueTimerStatus, WorkflowCommand, WorkflowState

NOW = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)


def _case_id(factory: sessionmaker[Session]) -> UUID:
    patient = Patient.register(
        PatientIdentifier("workflow-integration", f"P-{uuid4()}"),
        PersonName("An", "Nguyen"),
        Demographics(None, None),
        NOW,
    )
    encounter = Encounter.start(patient.id, "Emergency", NOW)
    case = ClinicalCase.open(encounter.id, "workflow persistence", ClinicalPriority.URGENT, NOW)
    with SQLAlchemyUnitOfWork(factory) as unit_of_work:
        unit_of_work.patients.add(patient)
        unit_of_work.encounters.add(encounter)
        unit_of_work.cases.add(case)
        unit_of_work.collect_events((patient, encounter, case))
        unit_of_work.commit()
    return case.id


def test_workflow_transition_effects_and_receipts_commit_together(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """A poor-quality ECG transition atomically persists state, task, alert, receipt, and outbox."""
    case_id = _case_id(postgres_session_factory)
    definition = load_demo_workflow_definition()
    handler = WorkflowCommandHandler(
        lambda: SQLAlchemyUnitOfWork(postgres_session_factory), definition
    )
    workflow = handler.start(case_id)
    handler.execute(workflow.id, WorkflowCommand("start_triage", 1, issued_at=NOW))
    handler.execute(workflow.id, WorkflowCommand("complete_triage", 2, issued_at=NOW))
    command = WorkflowCommand(
        "record_ecg",
        3,
        facts_patch={"ecg_available": True, "ecg_quality_acceptable": False},
        issued_at=NOW,
    )
    result = handler.execute(workflow.id, command)
    duplicate = handler.execute(workflow.id, command)

    assert result.state is WorkflowState.PHYSICIAN_REVIEW_REQUIRED
    assert duplicate.duplicate
    with postgres_session_factory() as session:
        record = session.get(ClinicalWorkflowRecord, workflow.id)
        assert record is not None
        assert record.current_state is WorkflowState.PHYSICIAN_REVIEW_REQUIRED
        assert (
            session.scalar(
                select(func.count())
                .select_from(ClinicalTaskRecord)
                .where(ClinicalTaskRecord.case_id == case_id)
            )
            == 2
        )
        assert (
            session.scalar(
                select(func.count()).select_from(AlertRecord).where(AlertRecord.case_id == case_id)
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkflowCommandReceiptRecord)
                .where(WorkflowCommandReceiptRecord.workflow_id == workflow.id)
            )
            == 3
        )


def test_due_timer_is_durably_completed_after_its_review_escalation(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """A persisted overdue timer produces one review transition and becomes completed."""
    case_id = _case_id(postgres_session_factory)
    definition = load_demo_workflow_definition()
    handler = WorkflowCommandHandler(
        lambda: SQLAlchemyUnitOfWork(postgres_session_factory), definition
    )
    workflow = handler.start(case_id)
    handler.execute(workflow.id, WorkflowCommand("start_triage", 1, issued_at=NOW))
    handler.execute(workflow.id, WorkflowCommand("complete_triage", 2, issued_at=NOW))
    handler.execute(
        workflow.id,
        WorkflowCommand(
            "record_ecg",
            3,
            facts_patch={"ecg_available": True, "ecg_quality_acceptable": True},
            issued_at=NOW,
        ),
    )
    handler.execute(
        workflow.id,
        WorkflowCommand("request_troponin", 4, due_at=NOW - timedelta(minutes=1), issued_at=NOW),
    )

    timer_service = WorkflowTimerService(
        lambda: SQLAlchemyUnitOfWork(postgres_session_factory), definition
    )
    assert timer_service.run_due_timers(NOW) == 1

    with postgres_session_factory() as session:
        record = session.get(ClinicalWorkflowRecord, workflow.id)
        timer = session.scalar(
            select(WorkflowDueTimerRecord).where(WorkflowDueTimerRecord.workflow_id == workflow.id)
        )
        assert record is not None
        assert timer is not None
        assert record.current_state is WorkflowState.PHYSICIAN_REVIEW_REQUIRED
        assert timer.status is DueTimerStatus.COMPLETED
