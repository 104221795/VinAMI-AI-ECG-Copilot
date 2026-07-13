"""Application command for persisting physician authority before workflow consumption."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from vinami.audit.domain.model import AuditEntry
from vinami.audit.ports.writer import AuditWriter
from vinami.shared.actor import ActorContext
from vinami.shared.domain import (
    DomainInvariantError,
    OptimisticConcurrencyError,
    require_utc,
    utc_now,
)
from vinami.shared.events.contracts import EventContext, EventEnvelope
from vinami.workflow.domain.decision import (
    PhysicianDecision,
    PhysicianDecisionStatus,
    PhysicianDecisionType,
)
from vinami.workflow.ports.repository import WorkflowUnitOfWork


@dataclass(frozen=True, slots=True)
class RecordPhysicianDecision:
    """Idempotent request to append one version-bound physician decision."""

    decision_id: UUID
    clinical_case_id: UUID
    workflow_id: UUID
    actor: ActorContext
    decision_type: PhysicianDecisionType
    decision_status: PhysicianDecisionStatus
    reason_code: str
    evidence_snapshot_reference: str
    workflow_version: int
    aggregate_expected_version: int
    occurred_at: datetime
    note: str | None = None
    corrects_decision_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class PhysicianDecisionResult:
    """Acknowledge whether the immutable command was newly recorded or duplicated."""

    decision: PhysicianDecision
    duplicate: bool


class RecordPhysicianDecisionHandler:
    """Verify actor and versions, then persist authority before it can be consumed."""

    def __init__(
        self,
        unit_of_work_factory: Callable[[], WorkflowUnitOfWork],
        audit_writer: AuditWriter,
    ) -> None:
        """Receive the production transaction boundary through dependency injection."""
        self._unit_of_work_factory = unit_of_work_factory
        self._audit_writer = audit_writer

    def execute(
        self,
        command: RecordPhysicianDecision,
        recorded_at: datetime | None = None,
    ) -> PhysicianDecisionResult:
        """Record the decision or append an immutable rejected-command audit entry."""
        try:
            return self._execute(command, recorded_at)
        except DomainInvariantError as error:
            self._audit_writer.append(
                AuditEntry(
                    id=command.decision_id,
                    case_id=command.clinical_case_id,
                    aggregate_type="PhysicianDecision",
                    aggregate_id=command.decision_id,
                    action="record_physician_decision",
                    occurred_at=require_utc(command.occurred_at, "occurred_at"),
                    actor_id=command.actor.actor_id,
                    actor_role=command.actor.actor_role,
                    prior_version=command.aggregate_expected_version,
                    resulting_version=None,
                    reason=str(error),
                    correlation_id=command.actor.correlation_id,
                    causation_id=command.actor.causation_id,
                    outcome="rejected",
                    payload={"decision_type": command.decision_type.value},
                )
            )
            raise

    def _execute(
        self,
        command: RecordPhysicianDecision,
        recorded_at: datetime | None = None,
    ) -> PhysicianDecisionResult:
        """Append an immutable decision and corresponding transactional outbox event."""
        command.actor.require_physician()
        decision = PhysicianDecision(
            decision_id=command.decision_id,
            clinical_case_id=command.clinical_case_id,
            actor_id=command.actor.actor_id,
            actor_role=command.actor.actor_role,
            decision_type=command.decision_type,
            decision_status=command.decision_status,
            reason_code=command.reason_code,
            note=command.note,
            evidence_snapshot_reference=command.evidence_snapshot_reference,
            workflow_version=command.workflow_version,
            aggregate_expected_version=command.aggregate_expected_version,
            occurred_at=require_utc(command.occurred_at, "occurred_at"),
            recorded_at=require_utc(recorded_at or utc_now(), "recorded_at"),
            correlation_id=command.actor.correlation_id,
            causation_id=command.actor.causation_id,
            corrects_decision_id=command.corrects_decision_id,
        )
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.physician_decisions.get(command.decision_id)
            if existing is not None:
                if existing != decision:
                    raise DomainInvariantError(
                        "decision_id was already used with a different command payload"
                    )
                return PhysicianDecisionResult(existing, duplicate=True)
            workflow = unit_of_work.workflows.get(command.workflow_id)
            clinical_case = unit_of_work.cases.get(command.clinical_case_id)
            if workflow is None or clinical_case is None:
                raise DomainInvariantError("physician decision requires an existing case workflow")
            if workflow.case_id != clinical_case.id:
                raise DomainInvariantError("workflow does not belong to physician decision case")
            if workflow.version != command.workflow_version:
                raise OptimisticConcurrencyError(
                    "physician decision was based on a stale workflow version"
                )
            if clinical_case.version != command.aggregate_expected_version:
                raise OptimisticConcurrencyError(
                    "physician decision was based on a stale clinical-case version"
                )
            persisted_role = unit_of_work.actors.role_for(command.actor.actor_id)
            if persisted_role != command.actor.actor_role:
                raise DomainInvariantError(
                    "actor context does not match the persisted clinical actor role"
                )
            if command.corrects_decision_id is not None:
                corrected = unit_of_work.physician_decisions.get(command.corrects_decision_id)
                if corrected is None or corrected.clinical_case_id != clinical_case.id:
                    raise DomainInvariantError("corrected decision does not exist for this case")
            unit_of_work.physician_decisions.add(decision)
            unit_of_work.stage_event(self._event(decision))
            unit_of_work.commit()
        return PhysicianDecisionResult(decision, duplicate=False)

    @staticmethod
    def _event(decision: PhysicianDecision) -> EventEnvelope:
        return EventEnvelope.from_context(
            event_type="PhysicianDecisionRecorded.v1",
            aggregate_type="PhysicianDecision",
            aggregate_id=decision.decision_id,
            aggregate_version=1,
            payload={
                "case_id": str(decision.clinical_case_id),
                "decision_id": str(decision.decision_id),
                "decision_type": decision.decision_type.value,
                "decision_status": decision.decision_status.value,
                "reason_code": decision.reason_code,
                "workflow_version": decision.workflow_version,
                "aggregate_expected_version": decision.aggregate_expected_version,
                "evidence_snapshot_reference": decision.evidence_snapshot_reference,
            },
            context=EventContext(
                correlation_id=decision.correlation_id,
                causation_id=decision.causation_id,
                actor_id=decision.actor_id,
                metadata={"actor_role": decision.actor_role},
            ),
        )
