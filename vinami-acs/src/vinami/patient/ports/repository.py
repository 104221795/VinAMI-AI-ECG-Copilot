"""Persistence ports for patient and encounter aggregate use cases."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.patient.domain.model import Encounter, Patient


class PatientRepository(Protocol):
    """Store and retrieve patient aggregates without exposing ORM records."""

    def add(self, patient: Patient) -> None:
        """Stage a registered patient for the active unit of work."""

    def get(self, patient_id: UUID) -> Patient | None:
        """Return one patient or ``None`` when the local record does not exist."""


class EncounterRepository(Protocol):
    """Store and retrieve encounter aggregates for known patients."""

    def add(self, encounter: Encounter) -> None:
        """Stage an encounter for the active unit of work."""

    def get(self, encounter_id: UUID) -> Encounter | None:
        """Return one encounter or ``None`` when it is absent."""
