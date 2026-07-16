"""Append-only audit value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from vinami.shared.domain import DomainInvariantError, require_text, require_utc


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Immutable audit item referencing, but never changing, an aggregate."""

    case_id: UUID | None
    aggregate_type: str
    aggregate_id: UUID
    action: str
    occurred_at: datetime
    actor_id: UUID | None
    actor_role: str | None
    prior_version: int | None
    resulting_version: int | None
    reason: str | None
    correlation_id: UUID
    causation_id: UUID | None
    outcome: str
    request_source: str = "internal"
    identity_subject: str | None = None
    actor_roles: tuple[str, ...] = ()
    applied_permission: str | None = None
    identity_provider: str | None = None
    authentication_method: str | None = None
    session_reference: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Require audit classification and UTC provenance."""
        object.__setattr__(
            self, "aggregate_type", require_text(self.aggregate_type, "aggregate_type")
        )
        object.__setattr__(self, "action", require_text(self.action, "audit action"))
        object.__setattr__(self, "outcome", require_text(self.outcome, "audit outcome"))
        object.__setattr__(
            self, "request_source", require_text(self.request_source, "request_source")
        )
        object.__setattr__(self, "occurred_at", require_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class Outcome:
    """Append-only physician-authored outcome revision for one Clinical Case."""

    case_id: UUID
    outcome_type: str
    outcome_timestamp: datetime
    final_conclusion: str
    recorded_at: datetime
    recorded_by: UUID
    actor_role: str
    revision_number: int
    record_version: int
    disposition: str | None = None
    destination: str | None = None
    cath_lab_review_outcome: str | None = None
    intervention_reference: str | None = None
    complications: str | None = None
    follow_up_status: str | None = None
    data_completeness: str = "documented"
    source: str = "physician_documented"
    uncertainty: str | None = None
    unavailable_reason: str | None = None
    supersedes_outcome_id: UUID | None = None
    correction_reason: str | None = None
    idempotency_key: str | None = None
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Preserve outcome as an authored fact, not an inferred platform conclusion."""
        object.__setattr__(self, "outcome_type", require_text(self.outcome_type, "outcome_type"))
        object.__setattr__(
            self, "final_conclusion", require_text(self.final_conclusion, "final_conclusion")
        )
        object.__setattr__(self, "actor_role", require_text(self.actor_role, "actor_role"))
        object.__setattr__(self, "source", require_text(self.source, "source"))
        object.__setattr__(
            self, "data_completeness", require_text(self.data_completeness, "data_completeness")
        )
        object.__setattr__(
            self, "outcome_timestamp", require_utc(self.outcome_timestamp, "outcome_timestamp")
        )
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))
        if self.revision_number < 1:
            raise DomainInvariantError("outcome revision_number must be positive")
        if self.record_version < 1:
            raise DomainInvariantError("outcome record_version must be positive")
        if self.supersedes_outcome_id is not None and not self.correction_reason:
            raise DomainInvariantError("outcome correction requires a correction reason")
