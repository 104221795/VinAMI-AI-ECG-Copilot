"""Patient and encounter aggregates with locally owned demographic facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import (
    AggregateRoot,
    DomainInvariantError,
    require_text,
    require_utc,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class PatientIdentifier:
    """Locally managed identifier; this MVP does not claim to be an EHR master index."""

    system: str
    value: str

    def __post_init__(self) -> None:
        """Require an explicit identifier namespace and value."""
        object.__setattr__(self, "system", require_text(self.system, "identifier system"))
        object.__setattr__(self, "value", require_text(self.value, "identifier value"))


@dataclass(frozen=True, slots=True)
class PersonName:
    """Patient name captured as entered, without diagnostic interpretation."""

    given_name: str
    family_name: str

    def __post_init__(self) -> None:
        """Reject blank name components."""
        object.__setattr__(self, "given_name", require_text(self.given_name, "given_name"))
        object.__setattr__(self, "family_name", require_text(self.family_name, "family_name"))


@dataclass(frozen=True, slots=True)
class Demographics:
    """Minimal demographic facts supplied for the local ACS workflow."""

    date_of_birth: date | None
    sex_at_birth: str | None

    def __post_init__(self) -> None:
        """Prevent future birth dates and blank optional values."""
        if self.date_of_birth is not None and self.date_of_birth > date.today():
            raise DomainInvariantError("date_of_birth cannot be in the future")
        if self.sex_at_birth is not None:
            object.__setattr__(
                self, "sex_at_birth", require_text(self.sex_at_birth, "sex_at_birth")
            )


class EncounterStatus(StrEnum):
    """Lifecycle state of a locally managed encounter."""

    ACTIVE = "active"
    DISCHARGED = "discharged"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Patient(AggregateRoot):
    """Patient aggregate owning locally captured identity and demographic facts."""

    identifier: PatientIdentifier
    name: PersonName
    demographics: Demographics
    registered_at: datetime

    @classmethod
    def register(
        cls,
        identifier: PatientIdentifier,
        name: PersonName,
        demographics: Demographics,
        registered_at: datetime | None = None,
        patient_id: UUID | None = None,
    ) -> Patient:
        """Register a local patient and emit the corresponding domain event."""
        patient = cls(
            id=patient_id or uuid4(),
            identifier=identifier,
            name=name,
            demographics=demographics,
            registered_at=require_utc(registered_at or utc_now(), "registered_at"),
        )
        patient._record_event(
            "PatientRegistered.v1",
            1,
            {"patient_id": str(patient.id), "identifier": identifier.value},
        )
        return patient


@dataclass(slots=True)
class Encounter(AggregateRoot):
    """Encounter aggregate that links a patient to a time-bounded local visit."""

    patient_id: UUID
    location: str
    status: EncounterStatus
    started_at: datetime
    ended_at: datetime | None = None
    external_reference: str | None = None

    @classmethod
    def start(
        cls,
        patient_id: UUID,
        location: str,
        started_at: datetime | None = None,
        encounter_id: UUID | None = None,
        external_reference: str | None = None,
    ) -> Encounter:
        """Start an active encounter for a known patient."""
        encounter = cls(
            id=encounter_id or uuid4(),
            patient_id=patient_id,
            location=require_text(location, "location"),
            status=EncounterStatus.ACTIVE,
            started_at=require_utc(started_at or utc_now(), "started_at"),
            external_reference=external_reference,
        )
        encounter._record_event(
            "EncounterStarted.v1",
            1,
            {"encounter_id": str(encounter.id), "patient_id": str(patient_id)},
        )
        return encounter

    def discharge(self, ended_at: datetime | None = None) -> None:
        """Close an active encounter while preserving its start provenance."""
        if self.status is not EncounterStatus.ACTIVE:
            raise DomainInvariantError("only an active encounter can be discharged")
        final_time = require_utc(ended_at or utc_now(), "ended_at")
        if final_time < self.started_at:
            raise DomainInvariantError("ended_at cannot precede started_at")
        self.status = EncounterStatus.DISCHARGED
        self.ended_at = final_time
