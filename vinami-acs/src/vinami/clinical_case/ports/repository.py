"""Persistence port for suspected ACS case lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from vinami.clinical_case.domain.model import ClinicalCase


@dataclass(frozen=True, slots=True)
class ClinicalCaseListRecord:
    """Case aggregate plus parent-owned location required by the queue read model."""

    clinical_case: ClinicalCase
    location: str


class ClinicalCaseRepository(Protocol):
    """Persist and retrieve clinical cases while preserving optimistic versions."""

    def add(self, case: ClinicalCase) -> None:
        """Stage a newly opened case."""

    def get(self, case_id: UUID) -> ClinicalCase | None:
        """Return one case or ``None``."""

    def save(self, case: ClinicalCase) -> None:
        """Stage a changed case using its aggregate version for concurrency control."""

    def get_active_for_encounter(self, encounter_id: UUID) -> ClinicalCase | None:
        """Return the active case for an encounter under the one-active-case policy."""

    def list_active(
        self,
        *,
        offset: int,
        limit: int,
        status: str | None,
        priority: str | None,
        location: str | None,
    ) -> tuple[list[ClinicalCaseListRecord], int]:
        """Return deterministic active-case rows and total count for the same filters."""
