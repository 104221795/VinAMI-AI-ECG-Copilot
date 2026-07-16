"""Transport-neutral R7 Command Center read-model contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CommandCenterTask:
    """Compact active-task projection for one queue case."""

    task_id: UUID
    task_type: str
    status: str
    priority: str
    due_at: datetime | None
    overdue_at: datetime | None
    escalation_level: int
    owner_user_id: UUID | None
    owner_team_id: UUID | None


@dataclass(frozen=True, slots=True)
class CommandCenterAlert:
    """Compact unresolved-alert projection for one queue case."""

    alert_id: UUID
    alert_type: str
    severity: str
    status: str
    raised_at: datetime
    escalation_level: int


@dataclass(frozen=True, slots=True)
class CommandCenterCase:
    """Persisted operational projection for one active ACS case."""

    case_id: UUID
    encounter_id: UUID
    patient_id: UUID
    patient_reference: str
    age_band: str | None
    sex_at_birth: str | None
    location: str
    case_status: str
    case_priority: str
    case_version: int
    opened_at: datetime
    workflow_id: UUID | None
    workflow_state: str | None
    workflow_version: int | None
    operational_priority: str
    priority_reason: str
    active_task_count: int
    overdue_task_count: int
    unresolved_alert_count: int
    next_due_at: datetime | None
    oldest_overdue_at: datetime | None
    owner_user_id: UUID | None
    owner_team_id: UUID | None
    snapshot_id: UUID | None
    snapshot_created_at: datetime | None
    evidence_status: str
    evidence_freshness: dict[str, str]
    missing_evidence: tuple[str, ...]
    technical_limits: tuple[str, ...]
    decision_id: UUID | None
    decision_type: str | None
    decision_rationale: str | None
    decision_recorded_at: datetime | None
    latest_activity_at: datetime
    update_token: str
    tasks: tuple[CommandCenterTask, ...]
    alerts: tuple[CommandCenterAlert, ...]


@dataclass(frozen=True, slots=True)
class CommandCenterQuery:
    """Validated filtering, ordering, visibility, and pagination inputs."""

    page: int
    page_size: int
    priority: str | None
    workflow_state: str | None
    overdue: bool | None
    alert_status: str | None
    evidence_status: str | None
    owner_id: UUID | None
    sort: str
    direction: str
    visible_locations: tuple[str, ...]
    now: datetime


class CommandCenterReadRepository(Protocol):
    """Read the R7 queue without exposing ORM records."""

    def list_active(self, query: CommandCenterQuery) -> tuple[list[CommandCenterCase], int]:
        """Return one deterministic page and its filtered total."""
