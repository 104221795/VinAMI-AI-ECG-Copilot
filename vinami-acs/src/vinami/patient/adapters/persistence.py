"""SQLAlchemy mappings and repositories for the Patient and Encounter context."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.patient.domain.model import (
    Demographics,
    Encounter,
    EncounterStatus,
    Patient,
    PatientIdentifier,
    PersonName,
)
from vinami.shared.persistence import Base, UTCDateTime, UUIDType


class PatientRecord(Base):
    """Infrastructure record for locally entered patient identity facts."""

    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("identifier_system", "identifier_value", name="uq_patient_identifier"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    identifier_system: Mapped[str] = mapped_column(String(100), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(120), nullable=False)
    given_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex_at_birth: Mapped[str | None] = mapped_column(String(50), nullable=True)
    age_band: Mapped[str | None] = mapped_column(String(40), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EncounterRecord(Base):
    """Infrastructure record for local encounters linked to one patient."""

    __tablename__ = "encounters"
    __table_args__ = (
        UniqueConstraint("external_reference", name="uq_encounter_external_reference"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    patient_id: Mapped[UUID] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    location: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[EncounterStatus] = mapped_column(
        Enum(EncounterStatus, name="encounter_status"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


def patient_to_record(patient: Patient) -> PatientRecord:
    """Map a framework-free patient aggregate into a new persistence record."""
    return PatientRecord(
        id=patient.id,
        identifier_system=patient.identifier.system,
        identifier_value=patient.identifier.value,
        given_name=patient.name.given_name if patient.name else None,
        family_name=patient.name.family_name if patient.name else None,
        date_of_birth=patient.demographics.date_of_birth,
        sex_at_birth=patient.demographics.sex_at_birth,
        age_band=patient.demographics.age_band,
        registered_at=patient.registered_at,
        updated_at=patient.updated_at,
        version=patient.version,
    )


def patient_from_record(record: PatientRecord) -> Patient:
    """Rehydrate a patient aggregate without emitting a new registration event."""
    return Patient(
        id=record.id,
        identifier=PatientIdentifier(record.identifier_system, record.identifier_value),
        name=(
            PersonName(record.given_name, record.family_name)
            if record.given_name is not None and record.family_name is not None
            else None
        ),
        demographics=Demographics(record.date_of_birth, record.sex_at_birth, record.age_band),
        registered_at=record.registered_at,
        updated_at=record.updated_at,
        version=record.version,
    )


def encounter_to_record(encounter: Encounter) -> EncounterRecord:
    """Map an encounter aggregate to persistence values."""
    return EncounterRecord(
        id=encounter.id,
        patient_id=encounter.patient_id,
        location=encounter.location,
        status=encounter.status,
        started_at=encounter.started_at,
        ended_at=encounter.ended_at,
        external_reference=encounter.external_reference,
        created_at=encounter.created_at,
        updated_at=encounter.updated_at,
        version=encounter.version,
    )


def encounter_from_record(record: EncounterRecord) -> Encounter:
    """Rehydrate an encounter aggregate without generating a start event."""
    return Encounter(
        id=record.id,
        patient_id=record.patient_id,
        location=record.location,
        status=record.status,
        started_at=record.started_at,
        ended_at=record.ended_at,
        external_reference=record.external_reference,
        created_at=record.created_at,
        updated_at=record.updated_at,
        version=record.version,
    )


class SQLAlchemyPatientRepository:
    """Patient repository bound to one explicit SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to the unit-of-work session."""
        self._session = session

    def add(self, patient: Patient) -> None:
        """Insert a newly registered patient; duplicate identifiers remain a database invariant."""
        if self._session.get(PatientRecord, patient.id) is not None:
            raise ValueError(f"patient {patient.id} already exists")
        self._session.add(patient_to_record(patient))

    def get(self, patient_id: UUID) -> Patient | None:
        """Retrieve a patient aggregate by UUID."""
        record = self._session.get(PatientRecord, patient_id)
        return patient_from_record(record) if record is not None else None

    def get_by_reference(self, system: str, value: str) -> Patient | None:
        """Retrieve a patient by the database-enforced reference scope."""
        record = self._session.scalar(
            select(PatientRecord).where(
                PatientRecord.identifier_system == system,
                PatientRecord.identifier_value == value,
            )
        )
        return patient_from_record(record) if record is not None else None


class SQLAlchemyEncounterRepository:
    """Encounter repository bound to one explicit SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to the unit-of-work session."""
        self._session = session

    def add(self, encounter: Encounter) -> None:
        """Insert an encounter linked to an existing patient."""
        if self._session.get(EncounterRecord, encounter.id) is not None:
            raise ValueError(f"encounter {encounter.id} already exists")
        self._session.add(encounter_to_record(encounter))

    def get(self, encounter_id: UUID) -> Encounter | None:
        """Retrieve an encounter aggregate by UUID."""
        record = self._session.get(EncounterRecord, encounter_id)
        return encounter_from_record(record) if record is not None else None
