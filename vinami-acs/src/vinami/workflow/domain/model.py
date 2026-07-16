"""Workflow aggregate and human task model for the VinAMI ACS demonstration MVP."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import (
    AggregateRoot,
    DomainInvariantError,
    OptimisticConcurrencyError,
    require_text,
    require_utc,
    utc_now,
)
from vinami.shared.events.contracts import EventContext
from vinami.workflow.domain.decision import PhysicianDecision, PhysicianDecisionType
from vinami.workflow.domain.definition import (
    DueTimer,
    DueTimerStatus,
    GeneratedAlert,
    GeneratedTask,
    TransitionExecution,
    WorkflowCommand,
    WorkflowDefinition,
    WorkflowFacts,
    WorkflowState,
    WorkflowTransitionHistory,
)
from vinami.workflow.domain.engine import WorkflowEngine


class TaskStatus(StrEnum):
    """Operational task state."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class TaskPriority(StrEnum):
    """Operational urgency without implying diagnostic certainty."""

    ROUTINE = "routine"
    PRIORITY = "priority"
    URGENT = "urgent"


@dataclass(frozen=True, slots=True)
class TaskTransition:
    """Immutable task lifecycle transition."""

    transition_id: UUID
    from_status: TaskStatus
    to_status: TaskStatus
    actor_id: UUID
    occurred_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TaskAssignment:
    """Assignment provenance for one clinical work item."""

    team_id: UUID | None
    user_id: UUID | None
    assigned_at: datetime

    def __post_init__(self) -> None:
        """Require an assignee and a UTC assignment time."""
        if self.team_id is None and self.user_id is None:
            raise DomainInvariantError("task assignment requires a team or user")
        object.__setattr__(self, "assigned_at", require_utc(self.assigned_at, "assigned_at"))


@dataclass(slots=True)
class ClinicalTask(AggregateRoot):
    """Task aggregate that records completion provenance and outcome."""

    case_id: UUID
    task_type: str
    status: TaskStatus
    created_at: datetime
    assignment: TaskAssignment | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    completed_by: UUID | None = None
    outcome: str | None = None
    workflow_id: UUID | None = None
    originating_decision_id: UUID | None = None
    source_type: str = "legacy"
    source_id: UUID | None = None
    priority: TaskPriority = TaskPriority.ROUTINE
    version: int = 1
    created_by: UUID | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    started_at: datetime | None = None
    started_by: UUID | None = None
    cancelled_at: datetime | None = None
    cancelled_by: UUID | None = None
    cancellation_reason: str | None = None
    overdue_at: datetime | None = None
    escalation_level: int = 0
    transition_history: list[TaskTransition] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        case_id: UUID,
        task_type: str,
        created_at: datetime | None = None,
        task_id: UUID | None = None,
        assignment: TaskAssignment | None = None,
        due_at: datetime | None = None,
        workflow_id: UUID | None = None,
        originating_decision_id: UUID | None = None,
        source_type: str = "legacy",
        source_id: UUID | None = None,
        priority: TaskPriority = TaskPriority.ROUTINE,
        created_by: UUID | None = None,
    ) -> ClinicalTask:
        """Create human work without interpreting evidence or activating treatment."""
        task = cls(
            id=task_id or uuid4(),
            case_id=case_id,
            task_type=require_text(task_type, "task_type"),
            status=TaskStatus.OPEN if source_type == "legacy" else TaskStatus.PENDING,
            created_at=require_utc(created_at or utc_now(), "created_at"),
            assignment=assignment,
            due_at=require_utc(due_at, "due_at") if due_at else None,
            workflow_id=workflow_id,
            originating_decision_id=originating_decision_id,
            source_type=require_text(source_type, "task source_type"),
            source_id=source_id,
            priority=priority,
            created_by=created_by,
        )
        task._record_event(
            "TaskCreated.v1",
            1,
            {"task_id": str(task.id), "case_id": str(case_id), "task_type": task.task_type},
        )
        return task

    def assign(self, assignment: TaskAssignment, actor_id: UUID) -> None:
        """Assign pending work to a user or team."""
        if self.status not in {TaskStatus.PENDING, TaskStatus.OPEN, TaskStatus.ASSIGNED}:
            raise DomainInvariantError("only pending work can be assigned")
        prior = self.status
        self.assignment = assignment
        self.status = TaskStatus.ASSIGNED
        self._transition(prior, self.status, actor_id, assignment.assigned_at)

    def acknowledge(self, actor_id: UUID, at: datetime | None = None) -> None:
        """Acknowledge assigned work without claiming completion."""
        if self.status is not TaskStatus.ASSIGNED:
            raise DomainInvariantError("only an assigned task can be acknowledged")
        occurred_at = require_utc(at or utc_now(), "acknowledged_at")
        self.acknowledged_at = occurred_at
        self.acknowledged_by = actor_id
        self.status = TaskStatus.ACKNOWLEDGED
        self._transition(TaskStatus.ASSIGNED, self.status, actor_id, occurred_at)

    def start_work(self, actor_id: UUID, at: datetime | None = None) -> None:
        """Start acknowledged work."""
        if self.status not in {TaskStatus.ACKNOWLEDGED, TaskStatus.OVERDUE}:
            raise DomainInvariantError("only acknowledged or overdue work can be started")
        occurred_at = require_utc(at or utc_now(), "started_at")
        prior = self.status
        self.started_at = occurred_at
        self.started_by = actor_id
        self.status = TaskStatus.IN_PROGRESS
        self._transition(prior, self.status, actor_id, occurred_at)

    def mark_overdue(self, actor_id: UUID, at: datetime | None = None) -> None:
        """Mark unfinished time-bound work overdue from authoritative backend time."""
        occurred_at = require_utc(at or utc_now(), "overdue_at")
        if self.due_at is None or occurred_at < self.due_at:
            raise DomainInvariantError("task is not due")
        if self.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.OVERDUE}:
            raise DomainInvariantError("task cannot be marked overdue from its current status")
        prior = self.status
        self.overdue_at = occurred_at
        self.status = TaskStatus.OVERDUE
        self._transition(prior, self.status, actor_id, occurred_at)

    def escalate(self, actor_id: UUID, at: datetime | None = None) -> None:
        """Increase escalation for authoritative overdue work."""
        if self.status is not TaskStatus.OVERDUE:
            raise DomainInvariantError("only overdue work can be escalated")
        occurred_at = require_utc(at or utc_now(), "escalated_at")
        self.escalation_level += 1
        self.version += 1
        self._record_event(
            "ClinicalTaskEscalated.v1",
            self.version,
            {
                "task_id": str(self.id),
                "case_id": str(self.case_id),
                "escalation_level": self.escalation_level,
                "occurred_at": occurred_at.isoformat(),
            },
            EventContext.start(actor_id=actor_id),
        )

    def complete(self, actor_id: UUID, outcome: str, completed_at: datetime | None = None) -> None:
        """Complete an open task with actor and outcome provenance."""
        if self.status not in {TaskStatus.IN_PROGRESS, TaskStatus.OPEN}:
            raise DomainInvariantError("only an in-progress task can be completed")
        prior = self.status
        self.status = TaskStatus.COMPLETED
        self.completed_by = actor_id
        self.completed_at = require_utc(completed_at or utc_now(), "completed_at")
        self.outcome = require_text(outcome, "task outcome")
        self._transition(prior, self.status, actor_id, self.completed_at, self.outcome)
        self._record_event(
            "ClinicalTaskCompleted.v1",
            self.version,
            {"task_id": str(self.id), "case_id": str(self.case_id), "actor_id": str(actor_id)},
            EventContext.start(actor_id=actor_id),
        )

    def cancel(self, actor_id: UUID, reason: str, at: datetime | None = None) -> None:
        """Cancel unfinished work with mandatory provenance."""
        if self.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            raise DomainInvariantError("completed or cancelled work cannot be cancelled")
        occurred_at = require_utc(at or utc_now(), "cancelled_at")
        prior = self.status
        self.status = TaskStatus.CANCELLED
        self.cancelled_at = occurred_at
        self.cancelled_by = actor_id
        self.cancellation_reason = require_text(reason, "cancellation_reason")
        self._transition(prior, self.status, actor_id, occurred_at, self.cancellation_reason)
        self._record_event(
            "ClinicalTaskCancelled.v1",
            self.version,
            {"task_id": str(self.id), "case_id": str(self.case_id), "reason": reason},
            EventContext.start(actor_id=actor_id),
        )

    def _transition(
        self,
        prior: TaskStatus,
        current: TaskStatus,
        actor_id: UUID,
        occurred_at: datetime,
        reason: str | None = None,
    ) -> None:
        self.version += 1
        self.transition_history.append(
            TaskTransition(uuid4(), prior, current, actor_id, occurred_at, reason)
        )
        self._record_event(
            "ClinicalTaskTransitioned.v1",
            self.version,
            {
                "task_id": str(self.id),
                "case_id": str(self.case_id),
                "from_status": prior.value,
                "to_status": current.value,
                "reason": reason,
            },
            EventContext.start(actor_id=actor_id),
        )


@dataclass(frozen=True, slots=True)
class WorkflowCommandResult:
    """Result for a command, including no-op duplicate delivery acknowledgement."""

    command_id: UUID
    state: WorkflowState
    transition_name: str | None
    duplicate: bool


@dataclass(slots=True)
class ClinicalWorkflow(AggregateRoot):
    """Versioned case workflow driven by typed transitions, guards, and effects."""

    case_id: UUID
    definition_id: str
    definition_version: str
    demonstration_notice: str
    state: WorkflowState = WorkflowState.NEW
    version: int = 1
    facts: WorkflowFacts = field(default_factory=WorkflowFacts)
    physician_decision_id: UUID | None = None
    transition_history: list[WorkflowTransitionHistory] = field(default_factory=list)
    due_timers: list[DueTimer] = field(default_factory=list)
    processed_command_ids: set[UUID] = field(default_factory=set)
    generated_tasks: list[GeneratedTask] = field(default_factory=list)
    generated_alerts: list[GeneratedAlert] = field(default_factory=list)
    last_transition_at: datetime | None = None

    @classmethod
    def start(
        cls,
        case_id: UUID,
        definition: WorkflowDefinition,
        workflow_id: UUID | None = None,
    ) -> ClinicalWorkflow:
        """Start a case-owned workflow from a validated demonstration definition."""
        return cls(
            id=workflow_id or uuid4(),
            case_id=case_id,
            definition_id=definition.definition_id,
            definition_version=definition.version,
            demonstration_notice=definition.notice,
        )

    def execute(
        self,
        definition: WorkflowDefinition,
        command: WorkflowCommand,
        engine: WorkflowEngine | None = None,
        decision: PhysicianDecision | None = None,
    ) -> WorkflowCommandResult:
        """Apply one idempotent command and record all configured state-change provenance."""
        self._require_matching_definition(definition)
        if command.command_id in self.processed_command_ids:
            return WorkflowCommandResult(command.command_id, self.state, None, duplicate=True)
        self._require_version(command.expected_version)
        self._authorize_command(command, decision)
        execution = (engine or WorkflowEngine()).apply(
            definition,
            self.state,
            self.facts,
            command,
            self.id,
        )
        self._apply_execution(command, execution, decision)
        return WorkflowCommandResult(
            command.command_id,
            self.state,
            execution.transition.name,
            duplicate=False,
        )

    def complete_due_timer(self, timer_id: UUID) -> None:
        """Mark one scheduled timer complete after its command has committed."""
        self.due_timers = [
            replace(timer, status=DueTimerStatus.COMPLETED) if timer.id == timer_id else timer
            for timer in self.due_timers
        ]

    def cancel_open_timers(self) -> None:
        """Cancel pending timers when a terminal workflow state is reached."""
        if self.state not in {WorkflowState.CLOSED, WorkflowState.CANCELLED}:
            return
        self.due_timers = [
            replace(timer, status=DueTimerStatus.CANCELLED)
            if timer.status is DueTimerStatus.SCHEDULED
            else timer
            for timer in self.due_timers
        ]

    def _apply_execution(
        self,
        command: WorkflowCommand,
        execution: TransitionExecution,
        decision: PhysicianDecision | None,
    ) -> None:
        prior_state = self.state
        self.state = execution.transition.to_state
        self.facts = execution.facts
        if decision is not None:
            self.physician_decision_id = decision.decision_id
        self.version += 1
        self.last_transition_at = command.issued_at
        self.processed_command_ids.add(command.command_id)
        self.transition_history.append(
            WorkflowTransitionHistory(
                id=uuid4(),
                command_id=command.command_id,
                transition_name=execution.transition.name,
                from_state=prior_state,
                to_state=self.state,
                actor_id=command.actor_id,
                actor_role=command.actor_role,
                occurred_at=command.issued_at,
                facts=self.facts,
            )
        )
        self.due_timers.extend(execution.timers)
        self.generated_tasks.extend(execution.tasks)
        self.generated_alerts.extend(execution.alerts)
        self.cancel_open_timers()
        self._record_event(
            "WorkflowTransitioned.v1",
            self.version,
            {
                "case_id": str(self.case_id),
                "command_id": str(command.command_id),
                "transition": execution.transition.name,
                "from_state": prior_state.value,
                "to_state": self.state.value,
                "demonstration_notice": self.demonstration_notice,
                "actor_role": command.actor_role,
                "decision_id": str(command.decision_id) if command.decision_id else None,
            },
            self._event_context(command),
        )
        self._record_effect_events(command, execution)
        self._record_authoritative_event(command)

    def _record_effect_events(
        self,
        command: WorkflowCommand,
        execution: TransitionExecution,
    ) -> None:
        for task in execution.tasks:
            self._record_event(
                "TaskCreated.v1",
                self.version,
                {
                    "case_id": str(self.case_id),
                    "task_id": str(task.id),
                    "task_type": task.task_type,
                    "workflow_command_id": str(command.command_id),
                },
                self._event_context(command),
            )
        for alert in execution.alerts:
            self._record_event(
                "AlertRaised.v1",
                self.version,
                {
                    "case_id": str(self.case_id),
                    "alert_id": str(alert.id),
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "workflow_command_id": str(command.command_id),
                },
                self._event_context(command),
            )
        for timer in execution.timers:
            self._record_event(
                "RepeatECGDue.v1"
                if timer.command_type == "repeat_ecg_due"
                else "PhysicianReviewRequested.v1",
                self.version,
                {
                    "case_id": str(self.case_id),
                    "timer_id": str(timer.id),
                    "timer_key": timer.key,
                    "due_at": timer.due_at.isoformat(),
                },
                self._event_context(command),
            )

    def _authorize_command(
        self, command: WorkflowCommand, decision: PhysicianDecision | None
    ) -> None:
        required_types = {
            "record_physician_decision": PhysicianDecisionType.PATHWAY_ACCEPTED,
            "request_transfer": PhysicianDecisionType.TRANSFER_REVIEW_REQUESTED,
            "request_cath_lab_review": PhysicianDecisionType.CATH_LAB_REVIEW_REQUESTED,
            "prepare_discharge_review": PhysicianDecisionType.DISCHARGE_REVIEW_APPROVED,
            "close_case": PhysicianDecisionType.CASE_CLOSURE_APPROVED,
        }
        required_type = required_types.get(command.command_type)
        if required_type is None:
            return
        if decision is None or command.decision_id != decision.decision_id:
            raise DomainInvariantError(
                f"{command.command_type} requires a persisted physician decision"
            )
        if not decision.is_effective:
            raise DomainInvariantError("revoked physician decision cannot authorize a transition")
        if decision.decision_type is not required_type:
            raise DomainInvariantError(
                f"{command.command_type} requires decision type {required_type.value}"
            )
        if decision.clinical_case_id != self.case_id:
            raise DomainInvariantError("physician decision belongs to another clinical case")
        if decision.actor_id != command.actor_id or decision.actor_role != command.actor_role:
            raise DomainInvariantError("workflow actor does not match physician decision actor")
        if decision.workflow_version != self.version:
            raise OptimisticConcurrencyError(
                "physician decision was not recorded for the current workflow version"
            )
        if decision.aggregate_expected_version != command.case_expected_version:
            raise OptimisticConcurrencyError(
                "physician decision and command disagree on clinical-case version"
            )

    def _record_authoritative_event(self, command: WorkflowCommand) -> None:
        event_types = {
            "request_transfer": "TransferRequested.v1",
            "request_cath_lab_review": "CathLabReviewRequested.v1",
        }
        event_type = event_types.get(command.command_type)
        if event_type is None:
            return
        self._record_event(
            event_type,
            self.version,
            {
                "case_id": str(self.case_id),
                "workflow_id": str(self.id),
                "decision_id": str(command.decision_id),
                "actor_role": command.actor_role,
            },
            self._event_context(command),
        )

    @staticmethod
    def _event_context(command: WorkflowCommand) -> EventContext:
        return EventContext(
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
            actor_id=command.actor_id,
            metadata={"actor_role": command.actor_role} if command.actor_role else {},
        )

    def _require_matching_definition(self, definition: WorkflowDefinition) -> None:
        if (
            self.definition_id != definition.definition_id
            or self.definition_version != definition.version
            or self.demonstration_notice != definition.notice
        ):
            raise DomainInvariantError("workflow definition does not match the workflow instance")

    def _require_version(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise OptimisticConcurrencyError(
                f"workflow {self.id} is version {self.version}, not expected {expected_version}"
            )
