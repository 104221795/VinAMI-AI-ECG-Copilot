"""Application commands and queries for the Patient and Encounter lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from vinami.patient.domain.model import Demographics, Encounter, Patient, PatientIdentifier
from vinami.patient.ports.repository import EncounterRepository, PatientRepository
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import (
    ActorContextError,
    IdempotencyConflictError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from vinami.shared.domain import require_text, require_utc
from vinami.shared.events.contracts import EventContext
from vinami.shared.idempotency import (
    IdempotencyRepository,
    IdempotencyResult,
    command_fingerprint,
)

PATIENT_REFERENCE_SYSTEM = "vinami.r1.synthetic"


class ActorRepository(Protocol):
    """Resolve development actor records without claiming authentication."""

    def role_for(self, actor_id: UUID) -> str | None:
        """Return the persisted role for one actor reference."""


class PatientLifecycleUnitOfWork(Protocol):
    """Minimal transaction port required by patient and encounter handlers."""

    patients: PatientRepository
    encounters: EncounterRepository
    actors: ActorRepository
    idempotency: IdempotencyRepository

    def __enter__(self) -> PatientLifecycleUnitOfWork: ...

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None: ...

    def collect_events(self, aggregates: list[Patient | Encounter]) -> None: ...

    def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Create one application transaction per command or query."""

    def __call__(self) -> PatientLifecycleUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class SafeDemographicSummary:
    """Non-identifying demographic summary exposed by the R1 API."""

    age_band: str | None = None
    sex_at_birth: str | None = None


@dataclass(frozen=True, slots=True)
class PatientDTO:
    """Application representation of a persisted Patient aggregate."""

    patient_id: UUID
    patient_reference: str
    reference_system: str
    safe_demographic_summary: SafeDemographicSummary
    created_at: datetime
    updated_at: datetime
    aggregate_version: int

    def to_document(self) -> dict[str, Any]:
        """Serialize the DTO for durable idempotency storage."""
        return {
            "patient_id": str(self.patient_id),
            "patient_reference": self.patient_reference,
            "reference_system": self.reference_system,
            "safe_demographic_summary": asdict(self.safe_demographic_summary),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "aggregate_version": self.aggregate_version,
        }

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> PatientDTO:
        """Rehydrate the original successful idempotent response."""
        summary = value["safe_demographic_summary"]
        return cls(
            patient_id=UUID(str(value["patient_id"])),
            patient_reference=str(value["patient_reference"]),
            reference_system=str(value["reference_system"]),
            safe_demographic_summary=SafeDemographicSummary(
                age_band=summary.get("age_band"), sex_at_birth=summary.get("sex_at_birth")
            ),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            updated_at=datetime.fromisoformat(str(value["updated_at"])),
            aggregate_version=int(value["aggregate_version"]),
        )


@dataclass(frozen=True, slots=True)
class EncounterDTO:
    """Application representation of a persisted Encounter aggregate."""

    encounter_id: UUID
    patient_id: UUID
    location: str
    status: str
    arrival_at: datetime
    created_at: datetime
    updated_at: datetime
    aggregate_version: int

    def to_document(self) -> dict[str, Any]:
        """Serialize the DTO for durable idempotency storage."""
        return {
            "encounter_id": str(self.encounter_id),
            "patient_id": str(self.patient_id),
            "location": self.location,
            "status": self.status,
            "arrival_at": self.arrival_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "aggregate_version": self.aggregate_version,
        }

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> EncounterDTO:
        """Rehydrate the original successful idempotent response."""
        return cls(
            encounter_id=UUID(str(value["encounter_id"])),
            patient_id=UUID(str(value["patient_id"])),
            location=str(value["location"]),
            status=str(value["status"]),
            arrival_at=datetime.fromisoformat(str(value["arrival_at"])),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            updated_at=datetime.fromisoformat(str(value["updated_at"])),
            aggregate_version=int(value["aggregate_version"]),
        )


@dataclass(frozen=True, slots=True)
class RegisterPatient:
    """Register a patient reference without collecting direct identity through R1."""

    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    patient_reference: str
    safe_demographic_summary: SafeDemographicSummary
    requested_at: datetime
    patient_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "idempotency_key", require_text(self.idempotency_key, "idempotency_key")
        )
        object.__setattr__(
            self,
            "patient_reference",
            require_text(self.patient_reference, "patient_reference"),
        )
        object.__setattr__(self, "requested_at", require_utc(self.requested_at, "requested_at"))


@dataclass(frozen=True, slots=True)
class StartEncounter:
    """Start an encounter for a persisted Patient."""

    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    patient_id: UUID
    location: str
    arrival_at: datetime
    external_reference: str | None = None
    encounter_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "idempotency_key", require_text(self.idempotency_key, "idempotency_key")
        )
        object.__setattr__(self, "location", require_text(self.location, "location"))
        object.__setattr__(self, "arrival_at", require_utc(self.arrival_at, "arrival_at"))
        if self.external_reference is not None:
            object.__setattr__(
                self,
                "external_reference",
                require_text(self.external_reference, "external_reference"),
            )


@dataclass(frozen=True, slots=True)
class GetPatient:
    """Retrieve a Patient by public UUID."""

    patient_id: UUID


@dataclass(frozen=True, slots=True)
class GetEncounter:
    """Retrieve an Encounter by public UUID."""

    encounter_id: UUID


class RegisterPatientHandler:
    """Coordinate unique Patient registration and atomic event/idempotency persistence."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def execute(self, command: RegisterPatient) -> PatientDTO:
        payload = {
            "patient_reference": command.patient_reference,
            "safe_demographic_summary": asdict(command.safe_demographic_summary),
        }
        fingerprint = command_fingerprint(payload)
        with self._unit_of_work() as unit_of_work:
            _validate_actor(unit_of_work.actors, command.actor)
            previous = unit_of_work.idempotency.lock_and_get(
                command.actor.actor_id, "RegisterPatient", command.idempotency_key
            )
            if previous is not None:
                _require_same_payload(previous, fingerprint)
                return PatientDTO.from_document(previous.response_payload)
            if (
                unit_of_work.patients.get_by_reference(
                    PATIENT_REFERENCE_SYSTEM, command.patient_reference
                )
                is not None
            ):
                raise ResourceConflictError("patient reference already exists")
            patient = Patient.register(
                PatientIdentifier(PATIENT_REFERENCE_SYSTEM, command.patient_reference),
                None,
                Demographics(
                    None,
                    command.safe_demographic_summary.sex_at_birth,
                    command.safe_demographic_summary.age_band,
                ),
                command.requested_at,
                patient_id=command.patient_id,
                context=_event_context(command.actor),
            )
            response = _patient_dto(patient)
            unit_of_work.patients.add(patient)
            unit_of_work.collect_events([patient])
            unit_of_work.idempotency.add(
                _idempotency_result(
                    command.actor,
                    "RegisterPatient",
                    command.idempotency_key,
                    command.command_id,
                    fingerprint,
                    "Patient",
                    patient.id,
                    response.to_document(),
                    command.requested_at,
                )
            )
            unit_of_work.commit()
            return response


class StartEncounterHandler:
    """Coordinate Encounter creation only for an existing Patient."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def execute(self, command: StartEncounter) -> EncounterDTO:
        payload = {
            "patient_id": str(command.patient_id),
            "location": command.location,
            "arrival_at": command.arrival_at.isoformat(),
            "external_reference": command.external_reference,
        }
        fingerprint = command_fingerprint(payload)
        with self._unit_of_work() as unit_of_work:
            _validate_actor(unit_of_work.actors, command.actor)
            previous = unit_of_work.idempotency.lock_and_get(
                command.actor.actor_id, "StartEncounter", command.idempotency_key
            )
            if previous is not None:
                _require_same_payload(previous, fingerprint)
                return EncounterDTO.from_document(previous.response_payload)
            if unit_of_work.patients.get(command.patient_id) is None:
                raise ResourceNotFoundError("patient not found")
            encounter = Encounter.start(
                command.patient_id,
                command.location,
                command.arrival_at,
                encounter_id=command.encounter_id,
                external_reference=command.external_reference,
                context=_event_context(command.actor),
            )
            response = _encounter_dto(encounter)
            unit_of_work.encounters.add(encounter)
            unit_of_work.collect_events([encounter])
            unit_of_work.idempotency.add(
                _idempotency_result(
                    command.actor,
                    "StartEncounter",
                    command.idempotency_key,
                    command.command_id,
                    fingerprint,
                    "Encounter",
                    encounter.id,
                    response.to_document(),
                    command.arrival_at,
                )
            )
            unit_of_work.commit()
            return response


class PatientQueryHandler:
    """Read Patient and Encounter aggregates through repository ports."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def get_patient(self, query: GetPatient) -> PatientDTO:
        with self._unit_of_work() as unit_of_work:
            patient = unit_of_work.patients.get(query.patient_id)
            if patient is None:
                raise ResourceNotFoundError("patient not found")
            return _patient_dto(patient)

    def get_encounter(self, query: GetEncounter) -> EncounterDTO:
        with self._unit_of_work() as unit_of_work:
            encounter = unit_of_work.encounters.get(query.encounter_id)
            if encounter is None:
                raise ResourceNotFoundError("encounter not found")
            return _encounter_dto(encounter)


def _validate_actor(repository: ActorRepository, actor: ActorContext) -> None:
    if repository.role_for(actor.actor_id) != actor.actor_role:
        raise ActorContextError("development actor reference is unknown or role does not match")


def _event_context(actor: ActorContext) -> EventContext:
    return EventContext(
        correlation_id=actor.correlation_id,
        causation_id=actor.causation_id,
        actor_id=actor.actor_id,
        metadata={"actor_role": actor.actor_role, "request_source": actor.request_source},
    )


def _require_same_payload(previous: IdempotencyResult, fingerprint: str) -> None:
    if previous.request_hash != fingerprint:
        raise IdempotencyConflictError("idempotency key was already used for another payload")


def _idempotency_result(
    actor: ActorContext,
    command_type: str,
    key: str,
    command_id: UUID,
    fingerprint: str,
    resource_type: str,
    resource_id: UUID,
    response_payload: dict[str, Any],
    created_at: datetime,
) -> IdempotencyResult:
    return IdempotencyResult(
        actor_id=actor.actor_id,
        command_type=command_type,
        idempotency_key=key,
        command_id=command_id,
        request_hash=fingerprint,
        resource_type=resource_type,
        resource_id=resource_id,
        response_payload=response_payload,
        created_at=created_at,
    )


def _patient_dto(patient: Patient) -> PatientDTO:
    return PatientDTO(
        patient_id=patient.id,
        patient_reference=patient.identifier.value,
        reference_system=patient.identifier.system,
        safe_demographic_summary=SafeDemographicSummary(
            age_band=patient.demographics.age_band,
            sex_at_birth=patient.demographics.sex_at_birth,
        ),
        created_at=patient.registered_at,
        updated_at=patient.updated_at,
        aggregate_version=patient.version,
    )


def _encounter_dto(encounter: Encounter) -> EncounterDTO:
    assert encounter.created_at is not None and encounter.updated_at is not None
    return EncounterDTO(
        encounter_id=encounter.id,
        patient_id=encounter.patient_id,
        location=encounter.location,
        status=encounter.status.value,
        arrival_at=encounter.started_at,
        created_at=encounter.created_at,
        updated_at=encounter.updated_at,
        aggregate_version=encounter.version,
    )
