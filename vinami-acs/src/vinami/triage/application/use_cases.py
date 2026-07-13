"""API-independent commands for structured, provenance-preserving ACS triage capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from vinami.triage.domain.model import DataStatus, Symptom, TriageAssessment, VitalMeasurement


@dataclass(frozen=True, slots=True)
class RecordSymptoms:
    """Record chief complaint, onset, pain, equivalents, history, and risk-factor facts."""

    case_id: UUID
    facts: tuple[Symptom, ...]

    @classmethod
    def structured(
        cls, case_id: UUID, category: str, value: str, status: DataStatus, at: datetime, source: str
    ) -> RecordSymptoms:
        """Build one explicit structured fact command."""
        return cls(
            case_id,
            (Symptom(category, status is DataStatus.KNOWN, at, source, value or None, status),),
        )


@dataclass(frozen=True, slots=True)
class RecordVitals:
    """Record an initial or repeated set of timestamped vital measurements."""

    case_id: UUID
    measurements: tuple[VitalMeasurement, ...]


def apply_symptoms(assessment: TriageAssessment, command: RecordSymptoms) -> None:
    """Apply a symptom command to its case-owned aggregate."""
    if assessment.case_id != command.case_id:
        raise ValueError("triage assessment does not belong to the command case")
    assessment.record_symptoms(list(command.facts))


def apply_vitals(assessment: TriageAssessment, command: RecordVitals) -> None:
    """Apply a vital-sign command to its case-owned aggregate."""
    if assessment.case_id != command.case_id:
        raise ValueError("triage assessment does not belong to the command case")
    assessment.record_vitals(list(command.measurements))
