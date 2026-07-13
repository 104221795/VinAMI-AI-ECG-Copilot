"""Recorded triage facts; these types intentionally make no diagnostic inference."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import (
    AggregateRoot,
    DomainInvariantError,
    require_text,
    require_utc,
)


class DataStatus(StrEnum):
    """Explicit availability of a triage datum without treating omission as absence."""

    KNOWN = "known"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Symptom:
    """A symptom fact as reported or observed with explicit provenance."""

    name: str
    present: bool
    recorded_at: datetime
    source: str
    note: str | None = None
    data_status: DataStatus = DataStatus.KNOWN

    def __post_init__(self) -> None:
        """Validate terminology and timestamp without interpreting the symptom."""
        object.__setattr__(self, "name", require_text(self.name, "symptom name"))
        object.__setattr__(self, "source", require_text(self.source, "symptom source"))
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))


@dataclass(frozen=True, slots=True)
class VitalMeasurement:
    """A single numeric vital observation with unit and collection provenance."""

    kind: str
    value: float
    unit: str
    recorded_at: datetime
    source: str

    def __post_init__(self) -> None:
        """Require finite, explicitly unit-bearing measurements."""
        if not self.value == self.value or self.value in (float("inf"), float("-inf")):
            raise DomainInvariantError("vital value must be finite")
        object.__setattr__(self, "kind", require_text(self.kind, "vital kind"))
        object.__setattr__(self, "unit", require_text(self.unit, "vital unit"))
        object.__setattr__(self, "source", require_text(self.source, "vital source"))
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))


@dataclass(slots=True)
class TriageAssessment(AggregateRoot):
    """Aggregate collecting factual symptoms and vitals for one clinical case."""

    case_id: UUID
    symptoms: list[Symptom]
    vitals: list[VitalMeasurement]

    @classmethod
    def create(cls, case_id: UUID, assessment_id: UUID | None = None) -> TriageAssessment:
        """Create an empty assessment; recorded facts are added by explicit commands."""
        return cls(id=assessment_id or uuid4(), case_id=case_id, symptoms=[], vitals=[])

    def record_symptoms(self, symptoms: list[Symptom]) -> None:
        """Append one non-empty symptom snapshot and emit an event."""
        if not symptoms:
            raise DomainInvariantError("symptoms must not be empty")
        self.symptoms.extend(symptoms)
        self._record_event(
            "SymptomsRecorded.v1",
            1,
            {"case_id": str(self.case_id), "count": len(symptoms)},
        )

    def record_vitals(self, vitals: list[VitalMeasurement]) -> None:
        """Append one non-empty vital set and emit an event."""
        if not vitals:
            raise DomainInvariantError("vitals must not be empty")
        self.vitals.extend(vitals)
        self._record_event(
            "VitalsRecorded.v1", 1, {"case_id": str(self.case_id), "count": len(vitals)}
        )

    def record_structured_fact(
        self, category: str, value: str, status: DataStatus, recorded_at: datetime, source: str
    ) -> None:
        """Store a structured triage fact, including explicitly missing or unknown data."""
        present = status is DataStatus.KNOWN
        self.record_symptoms(
            [
                Symptom(
                    name=require_text(category, "triage category"),
                    present=present,
                    recorded_at=recorded_at,
                    source=source,
                    note=require_text(value, "triage value") if value.strip() else None,
                    data_status=status,
                )
            ]
        )
