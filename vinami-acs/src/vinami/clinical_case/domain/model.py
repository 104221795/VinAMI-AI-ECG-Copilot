"""Suspected ACS case aggregate and lifecycle invariants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.actor import PHYSICIAN_ROLES
from vinami.shared.domain import (
    AggregateRoot,
    DomainInvariantError,
    OptimisticConcurrencyError,
    require_text,
    require_utc,
    utc_now,
)
from vinami.shared.events.contracts import EventContext


class CaseStatus(StrEnum):
    """Workflow state of a suspected ACS case, not a diagnosis."""

    OPEN = "open"
    UNDER_REVIEW = "under_review"
    CLOSED = "closed"


class ClinicalPriority(StrEnum):
    """Operational priority label chosen by a human workflow command."""

    ROUTINE = "routine"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class CaseClosureAuthorization:
    """Complete, version-bound authority required to close a reviewed clinical case."""

    command_id: UUID
    expected_version: int
    actor_id: UUID
    actor_role: str
    reason: str
    workflow_state: str
    physician_decision_id: UUID
    disposition_outcome_id: UUID
    unresolved_critical_alerts: int
    unresolved_consequential_tasks: int
    correlation_id: UUID
    causation_id: UUID | None
    occurred_at: datetime

    def __post_init__(self) -> None:
        """Validate structural authority and complete closure evidence."""
        if self.expected_version < 1:
            raise DomainInvariantError("expected_version must be at least one")
        if self.actor_role not in PHYSICIAN_ROLES:
            raise DomainInvariantError("case closure requires an authorized physician role")
        object.__setattr__(self, "reason", require_text(self.reason, "closure_reason"))
        object.__setattr__(
            self, "workflow_state", require_text(self.workflow_state, "workflow_state")
        )
        if self.unresolved_critical_alerts < 0 or self.unresolved_consequential_tasks < 0:
            raise DomainInvariantError("unresolved closure counts cannot be negative")
        object.__setattr__(self, "occurred_at", require_utc(self.occurred_at, "occurred_at"))


@dataclass(slots=True)
class ClinicalCase(AggregateRoot):
    """Aggregate owning the lifecycle of one suspected ACS case."""

    encounter_id: UUID
    opening_reason: str
    priority: ClinicalPriority
    status: CaseStatus
    opened_at: datetime
    version: int = 1
    closed_at: datetime | None = None
    closure_reason: str | None = None
    closed_by: UUID | None = None
    closure_actor_role: str | None = None
    closure_command_id: UUID | None = None
    closure_decision_id: UUID | None = None
    disposition_outcome_id: UUID | None = None

    @classmethod
    def open(
        cls,
        encounter_id: UUID,
        opening_reason: str,
        priority: ClinicalPriority,
        opened_at: datetime | None = None,
        case_id: UUID | None = None,
    ) -> ClinicalCase:
        """Open a case for one encounter and emit a lifecycle event."""
        case = cls(
            id=case_id or uuid4(),
            encounter_id=encounter_id,
            opening_reason=require_text(opening_reason, "opening_reason"),
            priority=priority,
            status=CaseStatus.OPEN,
            opened_at=require_utc(opened_at or utc_now(), "opened_at"),
        )
        case._record_event(
            "ClinicalCaseOpened.v1",
            case.version,
            {
                "case_id": str(case.id),
                "encounter_id": str(encounter_id),
                "opening_reason": case.opening_reason,
            },
        )
        return case

    def begin_review(self, expected_version: int) -> None:
        """Transition an open case to review with an explicit concurrency precondition."""
        self._require_version(expected_version)
        if self.status is not CaseStatus.OPEN:
            raise DomainInvariantError("only an open case can enter review")
        self.status = CaseStatus.UNDER_REVIEW
        self.version += 1

    def close(self, authorization: CaseClosureAuthorization) -> bool:
        """Close only with coordinated workflow, physician, alert, task, and outcome authority."""
        if self.closure_command_id == authorization.command_id:
            return True
        self._require_version(authorization.expected_version)
        if self.status is not CaseStatus.UNDER_REVIEW:
            raise DomainInvariantError("only a reviewed case can be closed")
        if authorization.workflow_state != "DISCHARGE_REVIEW":
            raise DomainInvariantError("case closure requires the discharge-review workflow state")
        if authorization.unresolved_critical_alerts:
            raise DomainInvariantError("unresolved critical alerts block case closure")
        if authorization.unresolved_consequential_tasks:
            raise DomainInvariantError("unresolved consequential tasks block case closure")
        self.status = CaseStatus.CLOSED
        self.closure_reason = authorization.reason
        self.closed_by = authorization.actor_id
        self.closure_actor_role = authorization.actor_role
        self.closure_command_id = authorization.command_id
        self.closure_decision_id = authorization.physician_decision_id
        self.disposition_outcome_id = authorization.disposition_outcome_id
        self.closed_at = authorization.occurred_at
        self.version += 1
        self._record_event(
            "CaseClosed.v1",
            self.version,
            {
                "case_id": str(self.id),
                "reason": self.closure_reason,
                "actor_id": str(authorization.actor_id),
                "actor_role": authorization.actor_role,
                "decision_id": str(authorization.physician_decision_id),
                "outcome_id": str(authorization.disposition_outcome_id),
                "prior_version": authorization.expected_version,
                "resulting_version": self.version,
            },
            EventContext(
                correlation_id=authorization.correlation_id,
                causation_id=authorization.causation_id,
                actor_id=authorization.actor_id,
                metadata={"actor_role": authorization.actor_role},
            ),
        )
        return False

    def _require_version(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise OptimisticConcurrencyError(
                f"case {self.id} is version {self.version}, not expected {expected_version}"
            )
