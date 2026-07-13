"""SQLAlchemy persistence for the versioned workflow engine and its generated work."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.alerts.adapters.persistence import AlertRecord
from vinami.alerts.domain.model import AlertSeverity, AlertStatus
from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType
from vinami.workflow.domain.definition import (
    DueTimer,
    DueTimerStatus,
    WorkflowFacts,
    WorkflowState,
    WorkflowTransitionHistory,
)
from vinami.workflow.domain.model import ClinicalTask, ClinicalWorkflow, TaskAssignment, TaskStatus


class ClinicalWorkflowRecord(Base):
    """Versioned workflow state owned by one clinical case."""

    __tablename__ = "clinical_workflows"
    __table_args__ = (UniqueConstraint("case_id", name="uq_clinical_workflow_case"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("clinical_cases.id", ondelete="CASCADE"))
    definition_id: Mapped[str] = mapped_column(String(160))
    definition_version: Mapped[str] = mapped_column(String(80))
    demonstration_notice: Mapped[str] = mapped_column(String(200))
    current_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState, name="workflow_state"), index=True
    )
    facts: Mapped[dict[str, object]] = mapped_column(JSONDocument)
    last_transition_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    physician_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("physician_decisions.decision_id", ondelete="RESTRICT"), nullable=True
    )

    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


class WorkflowTransitionHistoryRecord(Base):
    """Append-only accepted state-transition provenance."""

    __tablename__ = "workflow_transition_history"
    __table_args__ = (
        UniqueConstraint("workflow_id", "command_id", name="uq_workflow_transition_command"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_workflows.id", ondelete="CASCADE"), index=True
    )
    command_id: Mapped[UUID] = mapped_column(UUIDType, index=True)
    transition_name: Mapped[str] = mapped_column(String(160))
    from_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState, name="workflow_state", create_type=False)
    )
    to_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState, name="workflow_state", create_type=False)
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    facts: Mapped[dict[str, object]] = mapped_column(JSONDocument)


class WorkflowDueTimerRecord(Base):
    """Durable deferred workflow commands independent of worker lifetime."""

    __tablename__ = "workflow_due_timers"
    __table_args__ = (UniqueConstraint("workflow_id", "key", name="uq_workflow_timer_key"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_workflows.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(160))
    due_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    command_type: Mapped[str] = mapped_column(String(120))
    facts_patch: Mapped[dict[str, object]] = mapped_column(JSONDocument)
    status: Mapped[DueTimerStatus] = mapped_column(
        Enum(DueTimerStatus, name="workflow_due_timer_status"), index=True
    )


class WorkflowCommandReceiptRecord(Base):
    """Idempotency receipt for a workflow command."""

    __tablename__ = "workflow_command_receipts"

    command_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_workflows.id", ondelete="CASCADE"), index=True
    )
    resulting_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState, name="workflow_state", create_type=False)
    )
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ClinicalTaskRecord(Base):
    """Task record with workflow-effect provenance and human completion history."""

    __tablename__ = "clinical_tasks"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "workflow_command_id",
            "workflow_effect",
            name="uq_clinical_task_workflow_effect",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_command_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    workflow_effect: Mapped[str | None] = mapped_column(String(160), nullable=True)
    task_type: Mapped[str] = mapped_column(String(160), index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    assigned_team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_teams.id", ondelete="SET NULL"), nullable=True
    )
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    outcome: Mapped[str | None] = mapped_column(String(4000), nullable=True)


def task_from_record(record: ClinicalTaskRecord) -> ClinicalTask:
    """Rehydrate a task without recreating its emitted events."""
    assignment = None
    if record.assigned_at is not None:
        assignment = TaskAssignment(
            record.assigned_team_id, record.assigned_user_id, record.assigned_at
        )
    return ClinicalTask(
        id=record.id,
        case_id=record.case_id,
        task_type=record.task_type,
        status=record.status,
        created_at=record.created_at,
        assignment=assignment,
        due_at=record.due_at,
        completed_at=record.completed_at,
        completed_by=record.completed_by,
        outcome=record.outcome,
    )


class SQLAlchemyClinicalWorkflowRepository:
    """Persist workflow, transition history, idempotency, timers, tasks, and alerts together."""

    def __init__(self, session: Session) -> None:
        """Bind repository work to one explicit transaction."""
        self._session = session

    def add(self, workflow: ClinicalWorkflow) -> None:
        """Stage a new workflow instance from a validated definition."""
        self._session.add(self._record_from_workflow(workflow))

    def get(self, workflow_id: UUID) -> ClinicalWorkflow | None:
        """Return one workflow aggregate by its identifier."""
        record = self._session.get(ClinicalWorkflowRecord, workflow_id)
        return self._rehydrate(record) if record is not None else None

    def get_by_case_id(self, case_id: UUID) -> ClinicalWorkflow | None:
        """Return the one workflow associated with a clinical case."""
        record = self._session.scalar(
            select(ClinicalWorkflowRecord).where(ClinicalWorkflowRecord.case_id == case_id)
        )
        return self._rehydrate(record) if record is not None else None

    def save(self, workflow: ClinicalWorkflow) -> None:
        """Stage a state transition and every generated effect for the same unit of work."""
        record = self._session.get(ClinicalWorkflowRecord, workflow.id)
        if record is None:
            raise ValueError(f"workflow {workflow.id} does not exist")
        self._copy_fields(workflow, record)
        self._persist_history(workflow)
        self._persist_timers(workflow)
        self._persist_receipts(workflow)
        self._persist_effects(workflow)

    def due_timers(self, now: datetime) -> tuple[tuple[UUID, int, DueTimer], ...]:
        """Return due timers with their workflow's version for optimistic execution."""
        rows = self._session.execute(
            select(WorkflowDueTimerRecord, ClinicalWorkflowRecord)
            .join(
                ClinicalWorkflowRecord,
                ClinicalWorkflowRecord.id == WorkflowDueTimerRecord.workflow_id,
            )
            .where(
                WorkflowDueTimerRecord.status == DueTimerStatus.SCHEDULED,
                WorkflowDueTimerRecord.due_at <= now,
            )
            .order_by(WorkflowDueTimerRecord.due_at)
        ).all()
        return tuple(
            (workflow.id, workflow.version, self._timer(timer)) for timer, workflow in rows
        )

    def _rehydrate(self, record: ClinicalWorkflowRecord) -> ClinicalWorkflow:
        histories = list(
            self._session.scalars(
                select(WorkflowTransitionHistoryRecord)
                .where(WorkflowTransitionHistoryRecord.workflow_id == record.id)
                .order_by(WorkflowTransitionHistoryRecord.occurred_at)
            )
        )
        timers = list(
            self._session.scalars(
                select(WorkflowDueTimerRecord).where(
                    WorkflowDueTimerRecord.workflow_id == record.id
                )
            )
        )
        receipts = list(
            self._session.scalars(
                select(WorkflowCommandReceiptRecord).where(
                    WorkflowCommandReceiptRecord.workflow_id == record.id
                )
            )
        )
        return ClinicalWorkflow(
            id=record.id,
            case_id=record.case_id,
            definition_id=record.definition_id,
            definition_version=record.definition_version,
            demonstration_notice=record.demonstration_notice,
            state=record.current_state,
            version=record.version,
            facts=WorkflowFacts.from_document(record.facts),
            physician_decision_id=record.physician_decision_id,
            transition_history=[self._history(item) for item in histories],
            due_timers=[self._timer(item) for item in timers],
            processed_command_ids={item.command_id for item in receipts},
            last_transition_at=record.last_transition_at,
        )

    @staticmethod
    def _record_from_workflow(workflow: ClinicalWorkflow) -> ClinicalWorkflowRecord:
        record = ClinicalWorkflowRecord(id=workflow.id, case_id=workflow.case_id)
        SQLAlchemyClinicalWorkflowRepository._copy_fields(workflow, record)
        return record

    @staticmethod
    def _copy_fields(workflow: ClinicalWorkflow, record: ClinicalWorkflowRecord) -> None:
        record.definition_id = workflow.definition_id
        record.definition_version = workflow.definition_version
        record.demonstration_notice = workflow.demonstration_notice
        record.current_state = workflow.state
        record.facts = workflow.facts.as_document()
        record.last_transition_at = workflow.last_transition_at
        record.version = workflow.version
        record.physician_decision_id = workflow.physician_decision_id

    @staticmethod
    def _history(item: WorkflowTransitionHistoryRecord) -> WorkflowTransitionHistory:
        return WorkflowTransitionHistory(
            item.id,
            item.command_id,
            item.transition_name,
            item.from_state,
            item.to_state,
            item.actor_id,
            item.actor_role,
            item.occurred_at,
            WorkflowFacts.from_document(item.facts),
        )

    @staticmethod
    def _timer(item: WorkflowDueTimerRecord) -> DueTimer:
        return DueTimer(
            item.id, item.key, item.due_at, item.command_type, item.facts_patch, item.status
        )

    def _persist_history(self, workflow: ClinicalWorkflow) -> None:
        for item in workflow.transition_history:
            if self._session.get(WorkflowTransitionHistoryRecord, item.id) is None:
                self._session.add(
                    WorkflowTransitionHistoryRecord(
                        id=item.id,
                        workflow_id=workflow.id,
                        command_id=item.command_id,
                        transition_name=item.transition_name,
                        from_state=item.from_state,
                        to_state=item.to_state,
                        actor_id=item.actor_id,
                        actor_role=item.actor_role,
                        occurred_at=item.occurred_at,
                        facts=item.facts.as_document(),
                    )
                )

    def _persist_timers(self, workflow: ClinicalWorkflow) -> None:
        for timer in workflow.due_timers:
            record = self._session.get(WorkflowDueTimerRecord, timer.id)
            if record is None:
                self._session.add(
                    WorkflowDueTimerRecord(
                        id=timer.id,
                        workflow_id=workflow.id,
                        key=timer.key,
                        due_at=timer.due_at,
                        command_type=timer.command_type,
                        facts_patch=dict(timer.facts_patch),
                        status=timer.status,
                    )
                )
            else:
                record.status = timer.status

    def _persist_receipts(self, workflow: ClinicalWorkflow) -> None:
        history_by_command = {item.command_id: item for item in workflow.transition_history}
        for command_id in workflow.processed_command_ids:
            if self._session.get(WorkflowCommandReceiptRecord, command_id) is None:
                history = history_by_command[command_id]
                self._session.add(
                    WorkflowCommandReceiptRecord(
                        command_id=command_id,
                        workflow_id=workflow.id,
                        resulting_state=history.to_state,
                        processed_at=history.occurred_at,
                    )
                )

    def _persist_effects(self, workflow: ClinicalWorkflow) -> None:
        created_at = workflow.last_transition_at or datetime.now(UTC)
        for task in workflow.generated_tasks:
            if self._session.get(ClinicalTaskRecord, task.id) is None:
                self._session.add(
                    ClinicalTaskRecord(
                        id=task.id,
                        case_id=workflow.case_id,
                        workflow_id=workflow.id,
                        workflow_command_id=task.command_id,
                        workflow_effect=task.effect_name,
                        task_type=task.task_type,
                        status=TaskStatus.OPEN,
                        created_at=created_at,
                        due_at=task.due_at,
                    )
                )
        for alert in workflow.generated_alerts:
            if self._session.get(AlertRecord, alert.id) is None:
                self._session.add(
                    AlertRecord(
                        id=alert.id,
                        case_id=workflow.case_id,
                        workflow_id=workflow.id,
                        workflow_command_id=alert.command_id,
                        workflow_effect=alert.effect_name,
                        alert_type=alert.alert_type,
                        source="workflow_engine",
                        severity=AlertSeverity(alert.severity),
                        message=alert.message,
                        status=AlertStatus.ACTIVE,
                        raised_at=created_at,
                    )
                )


class SQLAlchemyClinicalTaskRepository:
    """Persist manually created human tasks and their completion provenance."""

    def __init__(self, session: Session) -> None:
        """Bind repository work to the current transaction."""
        self._session = session

    def add(self, task: ClinicalTask) -> None:
        """Stage a manually created task."""
        assignment = task.assignment
        self._session.add(
            ClinicalTaskRecord(
                id=task.id,
                case_id=task.case_id,
                task_type=task.task_type,
                status=task.status,
                created_at=task.created_at,
                due_at=task.due_at,
                assigned_team_id=assignment.team_id if assignment else None,
                assigned_user_id=assignment.user_id if assignment else None,
                assigned_at=assignment.assigned_at if assignment else None,
                completed_at=task.completed_at,
                completed_by=task.completed_by,
                outcome=task.outcome,
            )
        )

    def get(self, task_id: UUID) -> ClinicalTask | None:
        """Return a task by identifier."""
        record = self._session.get(ClinicalTaskRecord, task_id)
        return task_from_record(record) if record is not None else None

    def save(self, task: ClinicalTask) -> None:
        """Persist mutable completion state only."""
        record = self._session.get(ClinicalTaskRecord, task.id)
        if record is None:
            raise ValueError(f"task {task.id} does not exist")
        record.status = task.status
        record.completed_at = task.completed_at
        record.completed_by = task.completed_by
        record.outcome = task.outcome
