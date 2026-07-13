"""Persistence port for suspected ACS case lifecycle operations."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.clinical_case.domain.model import ClinicalCase


class ClinicalCaseRepository(Protocol):
    """Persist and retrieve clinical cases while preserving optimistic versions."""

    def add(self, case: ClinicalCase) -> None:
        """Stage a newly opened case."""

    def get(self, case_id: UUID) -> ClinicalCase | None:
        """Return one case or ``None``."""

    def save(self, case: ClinicalCase) -> None:
        """Stage a changed case using its aggregate version for concurrency control."""
