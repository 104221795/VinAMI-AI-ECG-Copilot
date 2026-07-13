"""Persistence port for ECG evidence and normalized AI results."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.ecg.domain.model import ECGStudy


class ECGStudyRepository(Protocol):
    """Persist and retrieve ECG study evidence without importing a model provider."""

    def add(self, study: ECGStudy) -> None:
        """Stage a newly uploaded ECG study."""

    def get(self, study_id: UUID) -> ECGStudy | None:
        """Return a study by UUID when it exists."""

    def save(self, study: ECGStudy) -> None:
        """Persist quality or normalized AI-result updates for a study."""
