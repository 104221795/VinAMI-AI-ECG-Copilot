"""Application services that execute workflow commands through explicit ports."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from vinami.audit.domain.model import AuditEntry
from vinami.audit.ports.writer import AuditWriter
from vinami.shared.domain import DomainInvariantError, utc_now
from vinami.workflow.domain.definition import (
    CONSEQUENTIAL_COMMAND_TYPES,
    WorkflowCommand,
    WorkflowDefinition,
)
from vinami.workflow.domain.engine import WorkflowEngine
from vinami.workflow.domain.model import ClinicalWorkflow, WorkflowCommandResult
from vinami.workflow.ports.repository import WorkflowUnitOfWork


class WorkflowCommandHandler:
    """Coordinate aggregate persistence and transactional outbox staging for workflow commands."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], WorkflowUnitOfWork],
        definition: WorkflowDefinition,
        engine: WorkflowEngine | None = None,
        audit_writer: AuditWriter | None = None,
    ) -> None:
        """Receive ports and the validated versioned definition through dependency injection."""
        self._unit_of_work_factory = unit_of_work_factory
        self._definition = definition
        self._engine = engine or WorkflowEngine()
        self._audit_writer = audit_writer

    def start(self, case_id: UUID, workflow_id: UUID | None = None) -> ClinicalWorkflow:
        """Create and persist a new case-owned workflow instance."""
        workflow = ClinicalWorkflow.start(case_id, self._definition, workflow_id)
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.workflows.add(workflow)
            unit_of_work.commit()
        return workflow

    def execute(self, workflow_id: UUID, command: WorkflowCommand) -> WorkflowCommandResult:
        """Execute a command and immutably audit rejected consequential attempts."""
        if command.command_type in CONSEQUENTIAL_COMMAND_TYPES and self._audit_writer is None:
            raise RuntimeError("consequential workflow commands require an audit writer")
        try:
            return self._execute(workflow_id, command)
        except DomainInvariantError as error:
            if command.command_type in CONSEQUENTIAL_COMMAND_TYPES:
                assert self._audit_writer is not None
                self._audit_writer.append(
                    AuditEntry(
                        id=command.command_id,
                        case_id=self._case_id(workflow_id),
                        aggregate_type="ClinicalWorkflow",
                        aggregate_id=workflow_id,
                        action=command.command_type,
                        occurred_at=command.issued_at,
                        actor_id=command.actor_id,
                        actor_role=command.actor_role,
                        prior_version=command.expected_version,
                        resulting_version=None,
                        reason=str(error),
                        correlation_id=command.correlation_id,
                        causation_id=command.causation_id,
                        outcome="rejected",
                        payload={"decision_id": str(command.decision_id)},
                    )
                )
            raise

    def _execute(self, workflow_id: UUID, command: WorkflowCommand) -> WorkflowCommandResult:
        """Load, execute, persist, and outbox-stage one idempotent workflow command."""
        if command.command_type == "close_case":
            raise DomainInvariantError(
                "close_case must use the coordinated clinical-case closure handler"
            )
        with self._unit_of_work_factory() as unit_of_work:
            workflow = unit_of_work.workflows.get(workflow_id)
            if workflow is None:
                raise DomainInvariantError(f"workflow {workflow_id} does not exist")
            decision = (
                unit_of_work.physician_decisions.get(command.decision_id)
                if command.decision_id is not None
                else None
            )
            if decision is not None:
                if not unit_of_work.physician_decisions.is_effective(decision.decision_id):
                    raise DomainInvariantError(
                        "physician decision is revoked or no longer effective"
                    )
                clinical_case = unit_of_work.cases.get(workflow.case_id)
                if clinical_case is None:
                    raise DomainInvariantError("workflow clinical case does not exist")
                if clinical_case.version != command.case_expected_version:
                    raise DomainInvariantError(
                        "workflow command does not match current clinical-case version"
                    )
                persisted_role = unit_of_work.actors.role_for(decision.actor_id)
                if persisted_role != decision.actor_role:
                    raise DomainInvariantError(
                        "physician decision actor is not authorized by persisted identity"
                    )
            result = workflow.execute(self._definition, command, self._engine, decision)
            if not result.duplicate:
                unit_of_work.workflows.save(workflow)
                unit_of_work.collect_events((workflow,))
                unit_of_work.commit()
            return result

    def _case_id(self, workflow_id: UUID) -> UUID | None:
        with self._unit_of_work_factory() as unit_of_work:
            workflow = unit_of_work.workflows.get(workflow_id)
            return workflow.case_id if workflow is not None else None


class WorkflowTimerService:
    """Convert persisted due timers into idempotent workflow commands inside a transaction."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], WorkflowUnitOfWork],
        definition: WorkflowDefinition,
        engine: WorkflowEngine | None = None,
    ) -> None:
        """Receive ports and definition via dependency injection."""
        self._unit_of_work_factory = unit_of_work_factory
        self._definition = definition
        self._engine = engine or WorkflowEngine()

    def run_due_timers(self, now: datetime | None = None) -> int:
        """Execute each currently due timer once, leaving stale entries safely retryable."""
        due_at = now or utc_now()
        processed = 0
        with self._unit_of_work_factory() as unit_of_work:
            timers = unit_of_work.workflows.due_timers(due_at)
            for workflow_id, expected_version, timer in timers:
                workflow = unit_of_work.workflows.get(workflow_id)
                if workflow is None:
                    continue
                command = WorkflowCommand(
                    command_type=timer.command_type,
                    expected_version=expected_version,
                    facts_patch=timer.facts_patch,
                    issued_at=due_at,
                    command_id=timer.id,
                )
                result = workflow.execute(self._definition, command, self._engine)
                if not result.duplicate:
                    workflow.complete_due_timer(timer.id)
                    unit_of_work.workflows.save(workflow)
                    unit_of_work.collect_events((workflow,))
                    processed += 1
            if processed:
                unit_of_work.commit()
        return processed
