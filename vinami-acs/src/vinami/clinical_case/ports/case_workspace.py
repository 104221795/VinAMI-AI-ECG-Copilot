"""Transport-neutral R8 complete case-workspace read contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CompleteCaseWorkspace:
    """Current, effective case evidence assembled without clinical recalculation."""

    case_id: UUID
    encounter_id: UUID
    patient_id: UUID
    patient_reference: str
    patient_name: str | None
    age_band: str | None
    sex_at_birth: str | None
    location: str
    encounter_status: str
    case_status: str
    case_priority: str
    opening_reason: str
    opened_at: datetime
    last_updated_at: datetime
    case_version: int
    triage: dict[str, object] | None
    vitals: dict[str, object] | None
    ecg: dict[str, object] | None
    troponin: dict[str, object]
    evidence_snapshot: dict[str, object] | None
    physician_assessment: dict[str, object] | None
    physician_decision: dict[str, object] | None
    workflow: dict[str, object] | None
    tasks: tuple[dict[str, object], ...]
    alerts: tuple[dict[str, object], ...]
    timeline: tuple[dict[str, object], ...]
    evidence_status: str
    missing_evidence: tuple[str, ...]
    stale_evidence: tuple[str, ...]
    technical_limits: tuple[str, ...]
    update_token: str
    evaluated_at: datetime


class CaseWorkspaceReadRepository(Protocol):
    """Read one location-scoped R8 workspace with bounded SQL queries."""

    def get(
        self, case_id: UUID, visible_locations: tuple[str, ...], now: datetime
    ) -> CompleteCaseWorkspace | None:
        """Return the visible case or ``None`` without leaking its existence."""
