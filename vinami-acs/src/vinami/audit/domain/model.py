"""Append-only audit value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from vinami.shared.domain import require_text, require_utc


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
    """Recorded outcome fact; it is not derived by any rule in this sprint."""

    case_id: UUID
    summary: str
    recorded_at: datetime
    recorded_by: UUID | None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Preserve non-empty outcome text and UTC provenance."""
        object.__setattr__(self, "summary", require_text(self.summary, "outcome summary"))
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))
