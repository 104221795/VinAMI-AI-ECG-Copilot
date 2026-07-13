"""Coordinated application command for safety-checked clinical-case closure."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from vinami.audit.domain.model import AuditEntry
from vinami.audit.ports.writer import AuditWriter
from vinami.clinical_case.domain.model import CaseClosureAuthorization
from vinami.shared.actor import ActorContext
from vinami.shared.domain import DomainInvariantError, OptimisticConcurrencyError, require_utc
from vinami.workflow.application.definitions import load_demo_workflow_definition
from vinami.workflow.domain.decision import PhysicianDecisionType
from vinami.workflow.domain.definition import WorkflowCommand, WorkflowState
from vinami.workflow.domain.engine import WorkflowEngine
from vinami.workflow.ports.repository import WorkflowUnitOfWork


@dataclass(frozen=True, slots=True)
class CloseClinicalCase:
    """Idempotent closure request with explicit actor, versions, reason, and decision."""

    command_id: UUID
    clinical_case_id: UUID
    workflow_id: UUID
    decision_id: UUID
    actor: ActorContext
    expected_case_version: int
    expected_workflow_version: int
    closure_reason: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class CloseClinicalCaseResult:
    """Return committed versions or acknowledge an exact duplicate command."""

    case_version: int
    workflow_version: int
    duplicate: bool


class CloseClinicalCaseHandler:
    """Close workflow and case atomically after validating all safety-owned evidence."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], WorkflowUnitOfWork],
        audit_writer: AuditWriter,
        engine: WorkflowEngine | None = None,
    ) -> None:
        """Receive ports and pure engine through dependency injection."""
        self._unit_of_work_factory = unit_of_work_factory
        self._audit_writer = audit_writer
        self._engine = engine or WorkflowEngine()
        self._definition = load_demo_workflow_definition()

    def execute(self, command: CloseClinicalCase) -> CloseClinicalCaseResult:
        """Close the case or append immutable rejected-command audit evidence."""
        try:
            return self._execute(command)
        except DomainInvariantError as error:
            self._audit_writer.append(
                AuditEntry(
                    id=command.command_id,
                    case_id=command.clinical_case_id,
                    aggregate_type="ClinicalCase",
                    aggregate_id=command.clinical_case_id,
                    action="close_clinical_case",
                    occurred_at=require_utc(command.occurred_at, "occurred_at"),
                    actor_id=command.actor.actor_id,
                    actor_role=command.actor.actor_role,
                    prior_version=command.expected_case_version,
                    resulting_version=None,
                    reason=str(error),
                    correlation_id=command.actor.correlation_id,
                    causation_id=command.actor.causation_id,
                    outcome="rejected",
                    payload={"decision_id": str(command.decision_id)},
                )
            )
            raise

    def _execute(self, command: CloseClinicalCase) -> CloseClinicalCaseResult:
        """Validate and commit closure without any clinical threshold logic."""
        command.actor.require_physician()
        occurred_at = require_utc(command.occurred_at, "occurred_at")
        with self._unit_of_work_factory() as unit_of_work:
            clinical_case = unit_of_work.cases.get(command.clinical_case_id)
            workflow = unit_of_work.workflows.get(command.workflow_id)
            decision = unit_of_work.physician_decisions.get(command.decision_id)
            if clinical_case is None or workflow is None or decision is None:
                raise DomainInvariantError(
                    "case closure requires existing case, workflow, and decision"
                )
            if clinical_case.closure_command_id == command.command_id:
                return CloseClinicalCaseResult(
                    clinical_case.version, workflow.version, duplicate=True
                )
            if (
                workflow.case_id != clinical_case.id
                or decision.clinical_case_id != clinical_case.id
            ):
                raise DomainInvariantError("closure resources do not belong to the same case")
            if clinical_case.version != command.expected_case_version:
                raise OptimisticConcurrencyError("case closure used a stale clinical-case version")
            if workflow.version != command.expected_workflow_version:
                raise OptimisticConcurrencyError("case closure used a stale workflow version")
            if decision.decision_type is not PhysicianDecisionType.CASE_CLOSURE_APPROVED:
                raise DomainInvariantError("case closure requires a closure-approved decision")
            if not decision.is_effective or not unit_of_work.physician_decisions.is_effective(
                decision.decision_id
            ):
                raise DomainInvariantError("revoked decision cannot authorize case closure")
            if (
                decision.actor_id != command.actor.actor_id
                or decision.actor_role != command.actor.actor_role
            ):
                raise DomainInvariantError(
                    "case closure actor does not match the physician decision"
                )
            if decision.workflow_version != workflow.version:
                raise OptimisticConcurrencyError("closure decision used a stale workflow version")
            if decision.aggregate_expected_version != clinical_case.version:
                raise OptimisticConcurrencyError("closure decision used a stale case version")
            if unit_of_work.actors.role_for(command.actor.actor_id) != command.actor.actor_role:
                raise DomainInvariantError("case closure actor role is not persisted or authorized")
            evidence = unit_of_work.closure_evidence.for_case(clinical_case.id)
            if evidence.disposition_outcome_id is None:
                raise DomainInvariantError("case closure requires a recorded disposition outcome")
            prior_workflow_state = workflow.state
            workflow_command = WorkflowCommand(
                command_type="close_case",
                expected_version=workflow.version,
                facts_patch={
                    "unresolved_critical_alerts": evidence.unresolved_critical_alerts,
                },
                actor_id=command.actor.actor_id,
                actor_role=command.actor.actor_role,
                decision_id=decision.decision_id,
                case_expected_version=clinical_case.version,
                correlation_id=command.actor.correlation_id,
                causation_id=command.actor.causation_id,
                issued_at=occurred_at,
                command_id=command.command_id,
            )
            workflow.execute(self._definition, workflow_command, self._engine, decision)
            authorization = CaseClosureAuthorization(
                command_id=command.command_id,
                expected_version=clinical_case.version,
                actor_id=command.actor.actor_id,
                actor_role=command.actor.actor_role,
                reason=command.closure_reason,
                workflow_state=prior_workflow_state.value,
                physician_decision_id=decision.decision_id,
                disposition_outcome_id=evidence.disposition_outcome_id,
                unresolved_critical_alerts=evidence.unresolved_critical_alerts,
                unresolved_consequential_tasks=evidence.unresolved_consequential_tasks,
                correlation_id=command.actor.correlation_id,
                causation_id=command.actor.causation_id,
                occurred_at=occurred_at,
            )
            clinical_case.close(authorization)
            unit_of_work.workflows.save(workflow)
            unit_of_work.cases.save(clinical_case)
            unit_of_work.collect_events((workflow, clinical_case))
            unit_of_work.commit()
            if workflow.state is not WorkflowState.CLOSED:
                raise RuntimeError("workflow closure did not reach CLOSED")
        return CloseClinicalCaseResult(clinical_case.version, workflow.version, duplicate=False)
