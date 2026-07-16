"""Real-time notification read service backed by committed outbox events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RealtimeNotification:
    """Backend-authoritative notification instructing clients to refetch."""

    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    occurred_at: datetime
    case_id: UUID | None
    resource_hint: str
    correlation_id: UUID
    safety_notice: str = "Real-time messages are notifications, not clinical truth."


class RealtimeEventRepository(Protocol):
    """Read port for committed notification events."""

    def events_since(
        self, last_event_id: UUID | None, case_id: UUID | None, limit: int
    ) -> list[RealtimeNotification]:
        """Return ordered notifications after an optional Last-Event-ID."""
        ...


class RealtimeQueryService:
    """Application read service for SSE and polling clients."""

    def __init__(self, repository: RealtimeEventRepository) -> None:
        self._repository = repository

    def events_since(
        self, last_event_id: UUID | None, case_id: UUID | None, limit: int = 50
    ) -> list[RealtimeNotification]:
        """Return a bounded ordered batch for reconnect-safe clients."""
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        return self._repository.events_since(last_event_id, case_id, limit)
