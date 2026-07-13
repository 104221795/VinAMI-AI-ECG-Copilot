"""Immutable, version-bound physician decisions consumed by the workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from vinami.shared.actor import PHYSICIAN_ROLES
from vinami.shared.domain import DomainInvariantError, require_text, require_utc


class PhysicianDecisionType(StrEnum):
    """Explicit authoritative decisions; none represents a diagnosis or AI action."""

    PATHWAY_ACCEPTED = "pathway_accepted"
    CATH_LAB_REVIEW_REQUESTED = "cath_lab_review_requested"
    TRANSFER_REVIEW_REQUESTED = "transfer_review_requested"
    DISCHARGE_REVIEW_APPROVED = "discharge_review_approved"
    CASE_CLOSURE_APPROVED = "case_closure_approved"


class PhysicianDecisionStatus(StrEnum):
    """Append-only status captured at creation; corrections use a new record."""

    ACTIVE = "active"
    CORRECTION = "correction"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class PhysicianDecision:
    """Persisted human authority bound to one case and exact aggregate versions."""

    decision_id: UUID
    clinical_case_id: UUID
    actor_id: UUID
    actor_role: str
    decision_type: PhysicianDecisionType
    decision_status: PhysicianDecisionStatus
    reason_code: str
    note: str | None
    evidence_snapshot_reference: str
    workflow_version: int
    aggregate_expected_version: int
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    corrects_decision_id: UUID | None = None

    def __post_init__(self) -> None:
        """Validate identity, authority, versions, text, and UTC provenance."""
        if self.decision_id.int == 0 or self.clinical_case_id.int == 0 or self.actor_id.int == 0:
            raise DomainInvariantError("physician decision identifiers must not be nil UUIDs")
        role = require_text(self.actor_role, "actor_role")
        if role not in PHYSICIAN_ROLES:
            raise DomainInvariantError(f"actor role {role!r} cannot record physician decisions")
        object.__setattr__(self, "actor_role", role)
        object.__setattr__(self, "reason_code", require_text(self.reason_code, "reason_code"))
        object.__setattr__(
            self,
            "evidence_snapshot_reference",
            require_text(self.evidence_snapshot_reference, "evidence_snapshot_reference"),
        )
        if self.note is not None:
            object.__setattr__(self, "note", require_text(self.note, "decision note"))
        if self.workflow_version < 1 or self.aggregate_expected_version < 1:
            raise DomainInvariantError("decision versions must be at least one")
        object.__setattr__(self, "occurred_at", require_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))
        if self.recorded_at < self.occurred_at:
            raise DomainInvariantError("recorded_at cannot precede occurred_at")
        if (
            self.corrects_decision_id is None
            and self.decision_status is not PhysicianDecisionStatus.ACTIVE
        ):
            raise DomainInvariantError(
                "correction or revocation must reference an earlier decision"
            )
        if (
            self.corrects_decision_id is not None
            and self.decision_status is PhysicianDecisionStatus.ACTIVE
        ):
            raise DomainInvariantError("a decision that references an earlier record must be typed")

    @property
    def is_effective(self) -> bool:
        """Return whether this immutable record can currently authorize an action."""
        return self.decision_status in {
            PhysicianDecisionStatus.ACTIVE,
            PhysicianDecisionStatus.CORRECTION,
        }
