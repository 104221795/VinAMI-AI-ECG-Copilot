"""Read-model ports for persisted lifecycle timeline and immutable audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TimelineReadRecord:
    """Transport-neutral persisted lifecycle timeline item."""

    timeline_event_id: UUID
    case_id: UUID
    event_type: str
    title: str
    occurred_at: datetime
    recorded_at: datetime
    source: str
    actor_id: UUID | None
    correlation_id: UUID
    causation_id: UUID | None


@dataclass(frozen=True, slots=True)
class AuditReadRecord:
    """Transport-neutral immutable audit item for a lifecycle resource chain."""

    audit_id: UUID
    actor_id: UUID | None
    actor_role: str | None
    identity_subject: str | None
    actor_roles: tuple[str, ...]
    applied_permission: str | None
    identity_provider: str | None
    authentication_method: str | None
    session_reference: str | None
    action: str
    resource_type: str
    resource_id: UUID
    request_source: str
    correlation_id: UUID
    causation_id: UUID | None
    prior_version: int | None
    resulting_version: int | None
    outcome: str
    reason: str | None
    recorded_at: datetime


class ClinicalLifecycleReadRepository(Protocol):
    """Read persisted timeline and audit rows without exposing ORM models."""

    def timeline_for_case(self, case_id: UUID) -> list[TimelineReadRecord]:
        """Return a case-scoped lifecycle timeline in deterministic order."""

    def audit_for_case(self, case_id: UUID) -> list[AuditReadRecord]:
        """Return immutable patient/encounter/case audit rows in deterministic order."""
