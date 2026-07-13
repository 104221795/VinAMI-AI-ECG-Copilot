"""Framework-free domain primitives shared by VinAMI bounded contexts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from vinami.shared.events.contracts import EventContext, EventEnvelope


class DomainInvariantError(ValueError):
    """Raised when an aggregate command would violate a declared invariant."""


class OptimisticConcurrencyError(DomainInvariantError):
    """Raised when a command was based on an obsolete aggregate version."""


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for domain provenance."""
    return datetime.now(UTC)


def require_utc(value: datetime, field_name: str) -> datetime:
    """Validate and normalize a timestamp to UTC."""
    if value.tzinfo is None:
        raise DomainInvariantError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def require_text(value: str, field_name: str) -> str:
    """Validate a non-empty text value without silently changing clinical facts."""
    if not value.strip():
        raise DomainInvariantError(f"{field_name} must not be blank")
    return value.strip()


@dataclass(slots=True)
class AggregateRoot:
    """Base behavior for aggregates that emit events but expose no mutable event list."""

    id: UUID
    _events: list[EventEnvelope] = field(default_factory=list, init=False, repr=False)

    def _record_event(
        self,
        event_type: str,
        aggregate_version: int,
        payload: dict[str, Any],
        context: EventContext | None = None,
        event_version: int = 1,
    ) -> None:
        """Record an immutable event for persistence by the transactional outbox."""
        self._events.append(
            EventEnvelope.from_context(
                event_type=event_type,
                event_version=event_version,
                aggregate_type=type(self).__name__,
                aggregate_id=self.id,
                aggregate_version=aggregate_version,
                payload=payload,
                context=context,
            )
        )

    def pull_events(self) -> tuple[EventEnvelope, ...]:
        """Return and clear events after a unit of work has staged them in the outbox."""
        events = tuple(self._events)
        self._events.clear()
        return events
