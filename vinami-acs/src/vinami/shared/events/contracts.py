"""Framework-free contracts for durable, versioned internal events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import UUID, uuid4


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value.strip()


@runtime_checkable
class DomainEvent(Protocol):
    """Minimal event protocol consumed by the outbox without aggregate coupling."""

    event_id: UUID
    event_type: str
    event_version: int
    aggregate_type: str
    aggregate_id: UUID
    aggregate_version: int
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    actor_id: UUID | None
    payload: dict[str, Any]
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EventContext:
    """Command-scoped provenance propagated to events emitted by an aggregate."""

    correlation_id: UUID
    causation_id: UUID | None = None
    actor_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def start(
        cls, actor_id: UUID | None = None, metadata: dict[str, Any] | None = None
    ) -> EventContext:
        """Create a root correlation context for one command or external message."""
        return cls(correlation_id=uuid4(), actor_id=actor_id, metadata=metadata or {})


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Immutable durable envelope shared by the outbox and internal dispatcher."""

    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    aggregate_version: int
    payload: dict[str, Any]
    event_version: int = 1
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    actor_id: UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        """Validate versioning and provenance fields before persistence."""
        object.__setattr__(self, "event_type", _text(self.event_type, "event_type"))
        object.__setattr__(self, "aggregate_type", _text(self.aggregate_type, "aggregate_type"))
        object.__setattr__(self, "occurred_at", _utc(self.occurred_at, "occurred_at"))
        if self.event_version < 1:
            raise ValueError("event_version must be at least one")
        if self.aggregate_version < 1:
            raise ValueError("aggregate_version must be at least one")

    @classmethod
    def from_context(
        cls,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        aggregate_version: int,
        payload: dict[str, Any],
        context: EventContext | None = None,
        event_version: int = 1,
    ) -> EventEnvelope:
        """Create an envelope while propagating optional command provenance."""
        resolved_context = context or EventContext.start()
        return cls(
            event_type=event_type,
            event_version=event_version,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            correlation_id=resolved_context.correlation_id,
            causation_id=resolved_context.causation_id,
            actor_id=resolved_context.actor_id,
            payload=payload,
            metadata=dict(resolved_context.metadata),
        )


class OutboxStatus(StrEnum):
    """Durable delivery state for an internal event envelope."""

    PENDING = "pending"
    PROCESSING = "processing"
    PUBLISHED = "published"
    DEAD_LETTER = "dead_letter"
