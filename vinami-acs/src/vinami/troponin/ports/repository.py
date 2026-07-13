"""Persistence port for the TroponinTimeline aggregate."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.troponin.domain.model import TroponinTimeline


class TroponinTimelineRepository(Protocol):
    """Persist and rehydrate a case-owned troponin timeline."""

    def add(self, timeline: TroponinTimeline) -> None:
        """Stage a new timeline."""

    def get_by_case_id(self, case_id: UUID) -> TroponinTimeline | None:
        """Return the one timeline for a case, when present."""

    def save(self, timeline: TroponinTimeline) -> None:
        """Persist ordered, collected, and resulted timeline changes."""
