"""R2 commands and queries for auditable triage and vital documentation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID

from vinami.clinical_case.domain.model import CaseStatus, ClinicalCase
from vinami.clinical_case.ports.repository import ClinicalCaseRepository
from vinami.patient.application.lifecycle import ActorRepository
from vinami.patient.ports.repository import EncounterRepository
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import (
    ActorContextError,
    IdempotencyConflictError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from vinami.shared.domain import OptimisticConcurrencyError, require_text, require_utc, utc_now
from vinami.shared.events.contracts import EventContext
from vinami.shared.idempotency import (
    IdempotencyRepository,
    IdempotencyResult,
    command_fingerprint,
)
from vinami.triage.application.completeness import (
    DocumentationCompletenessPolicy,
    MissingDocumentationItem,
)
from vinami.triage.domain.model import (
    ObservationState,
    OnsetPrecision,
    StructuredObservation,
    TriageAssessment,
    TriageContentValues,
    TriageRecordStatus,
    VitalContentValues,
    VitalMeasurement,
    VitalObservationSet,
)
from vinami.triage.ports.repository import ClinicalDocumentationRepository


class ClinicalDocumentationUnitOfWork(Protocol):
    """Transaction port required by R2 documentation commands and queries."""

    cases: ClinicalCaseRepository
    encounters: EncounterRepository
    actors: ActorRepository
    idempotency: IdempotencyRepository
    documentation: ClinicalDocumentationRepository

    def __enter__(self) -> ClinicalDocumentationUnitOfWork: ...

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None: ...

    def collect_events(self, aggregates: list[TriageAssessment | VitalObservationSet]) -> None: ...

    def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Create one explicit database transaction."""

    def __call__(self) -> ClinicalDocumentationUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class TriageContent:
    """Typed factual content shared by record and correction commands."""

    chief_complaint: str | None = None
    symptom_onset_state: ObservationState = ObservationState.NOT_ASSESSED
    symptom_onset_at: datetime | None = None
    symptom_onset_precision: OnsetPrecision | None = None
    symptom_description: str | None = None
    symptom_location: str | None = None
    symptom_radiation: str | None = None
    symptom_duration: str | None = None
    symptom_pattern: str | None = None
    aggravating_factors: str | None = None
    relieving_factors: str | None = None
    relevant_history_summary: str | None = None
    current_medication_summary: str | None = None
    allergy_summary: str | None = None
    clinical_note: str | None = None
    associated_symptoms: tuple[StructuredObservation, ...] = ()
    cardiovascular_risk_factors: tuple[StructuredObservation, ...] = ()

    def as_domain_arguments(self) -> TriageContentValues:
        """Return only aggregate content fields."""
        return {
            "chief_complaint": self.chief_complaint,
            "symptom_onset_state": self.symptom_onset_state,
            "symptom_onset_at": self.symptom_onset_at,
            "symptom_onset_precision": self.symptom_onset_precision,
            "symptom_description": self.symptom_description,
            "symptom_location": self.symptom_location,
            "symptom_radiation": self.symptom_radiation,
            "symptom_duration": self.symptom_duration,
            "symptom_pattern": self.symptom_pattern,
            "aggravating_factors": self.aggravating_factors,
            "relieving_factors": self.relieving_factors,
            "relevant_history_summary": self.relevant_history_summary,
            "current_medication_summary": self.current_medication_summary,
            "allergy_summary": self.allergy_summary,
            "clinical_note": self.clinical_note,
            "associated_symptoms": self.associated_symptoms,
            "cardiovascular_risk_factors": self.cardiovascular_risk_factors,
        }

    def fingerprint_document(self) -> dict[str, object]:
        """Normalize enums and timestamps for durable idempotency comparison."""
        document: dict[str, object] = dict(self.as_domain_arguments())
        document["associated_symptoms"] = [
            _structured_observation_document(value) for value in self.associated_symptoms
        ]
        document["cardiovascular_risk_factors"] = [
            _structured_observation_document(value) for value in self.cardiovascular_risk_factors
        ]
        return cast(dict[str, object], _json_value(document))


@dataclass(frozen=True, slots=True)
class VitalContent:
    """Typed content shared by vital record and correction commands."""

    measurements: tuple[VitalMeasurement, ...]
    device_reference: str | None = None
    supplemental_oxygen_state: ObservationState = ObservationState.NOT_ASSESSED
    oxygen_delivery_method: str | None = None
    level_of_consciousness: str | None = None
    observation_note: str | None = None

    def as_domain_arguments(self) -> VitalContentValues:
        return {
            "device_reference": self.device_reference,
            "supplemental_oxygen_state": self.supplemental_oxygen_state,
            "oxygen_delivery_method": self.oxygen_delivery_method,
            "level_of_consciousness": self.level_of_consciousness,
            "observation_note": self.observation_note,
        }

    def fingerprint_document(self) -> dict[str, object]:
        return {
            **_json_value(self.as_domain_arguments()),
            "measurements": [_measurement_document(value) for value in self.measurements],
        }


@dataclass(frozen=True, slots=True)
class RecordTriageAssessment:
    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    clinical_case_id: UUID
    expected_case_version: int
    occurred_at: datetime
    source: str
    content: TriageContent
    assessment_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "idempotency_key", require_text(self.idempotency_key, "key"))
        object.__setattr__(self, "source", require_text(self.source, "source"))
        object.__setattr__(self, "occurred_at", require_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class CorrectTriageAssessment:
    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    clinical_case_id: UUID
    assessment_id: UUID
    expected_record_version: int
    occurred_at: datetime
    source: str
    correction_reason: str
    content: TriageContent
    correction_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "idempotency_key", require_text(self.idempotency_key, "key"))
        object.__setattr__(self, "source", require_text(self.source, "source"))
        object.__setattr__(
            self, "correction_reason", require_text(self.correction_reason, "correction_reason")
        )
        object.__setattr__(self, "occurred_at", require_utc(self.occurred_at, "occurred_at"))


@dataclass(frozen=True, slots=True)
class RecordVitalObservationSet:
    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    clinical_case_id: UUID
    expected_case_version: int
    observed_at: datetime
    source: str
    content: VitalContent
    vital_set_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "idempotency_key", require_text(self.idempotency_key, "key"))
        object.__setattr__(self, "source", require_text(self.source, "source"))
        object.__setattr__(self, "observed_at", require_utc(self.observed_at, "observed_at"))


@dataclass(frozen=True, slots=True)
class CorrectVitalObservationSet:
    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    clinical_case_id: UUID
    vital_set_id: UUID
    expected_record_version: int
    observed_at: datetime
    source: str
    correction_reason: str
    content: VitalContent
    correction_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "idempotency_key", require_text(self.idempotency_key, "key"))
        object.__setattr__(self, "source", require_text(self.source, "source"))
        object.__setattr__(
            self, "correction_reason", require_text(self.correction_reason, "correction_reason")
        )
        object.__setattr__(self, "observed_at", require_utc(self.observed_at, "observed_at"))


@dataclass(frozen=True, slots=True)
class TriageAssessmentDTO:
    assessment: TriageAssessment

    def to_document(self) -> dict[str, Any]:
        return _triage_document(self.assessment)

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> TriageAssessmentDTO:
        return cls(_triage_from_document(value))


@dataclass(frozen=True, slots=True)
class VitalObservationSetDTO:
    vital_set: VitalObservationSet

    def to_document(self) -> dict[str, Any]:
        return _vital_document(self.vital_set)

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> VitalObservationSetDTO:
        return cls(_vital_from_document(value))


@dataclass(frozen=True, slots=True)
class TriageVitalsSummaryDTO:
    current_triage: TriageAssessment | None
    latest_vitals: VitalObservationSet | None
    recent_vitals: tuple[VitalObservationSet, ...]
    missing_documentation: tuple[MissingDocumentationItem, ...]
    completeness_policy_version: str
    data_freshness_at: datetime
    case_version: int


class RecordTriageAssessmentHandler:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def execute(self, command: RecordTriageAssessment) -> TriageAssessmentDTO:
        payload = {
            "case_id": str(command.clinical_case_id),
            "expected_case_version": command.expected_case_version,
            "occurred_at": command.occurred_at.isoformat(),
            "source": command.source,
            "content": command.content.fingerprint_document(),
        }
        fingerprint = command_fingerprint(payload)
        with self._unit_of_work() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow, command.actor, "RecordTriageAssessment", command.idempotency_key, fingerprint
            )
            if previous is not None:
                return TriageAssessmentDTO.from_document(previous.response_payload)
            case = _writable_case(uow, command.clinical_case_id, command.expected_case_version)
            if uow.documentation.current_triage(case.id) is not None:
                raise ResourceConflictError("triage already exists; use the correction command")
            now = utc_now()
            assessment = TriageAssessment.record(
                assessment_id=command.assessment_id,
                clinical_case_id=case.id,
                source=command.source,
                actor_id=command.actor.actor_id,
                actor_role=command.actor.actor_role,
                occurred_at=command.occurred_at,
                recorded_at=now,
                context=_context(command.actor),
                **command.content.as_domain_arguments(),
            )
            response = TriageAssessmentDTO(assessment)
            uow.documentation.add_triage(assessment)
            uow.collect_events([assessment])
            _store_idempotency(
                uow,
                command,
                "RecordTriageAssessment",
                fingerprint,
                assessment.id,
                response.to_document(),
                now,
            )
            uow.commit()
            return response


class CorrectTriageAssessmentHandler:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def execute(self, command: CorrectTriageAssessment) -> TriageAssessmentDTO:
        payload = {
            "case_id": str(command.clinical_case_id),
            "assessment_id": str(command.assessment_id),
            "expected_record_version": command.expected_record_version,
            "occurred_at": command.occurred_at.isoformat(),
            "source": command.source,
            "reason": command.correction_reason,
            "content": command.content.fingerprint_document(),
        }
        fingerprint = command_fingerprint(payload)
        with self._unit_of_work() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow, command.actor, "CorrectTriageAssessment", command.idempotency_key, fingerprint
            )
            if previous is not None:
                return TriageAssessmentDTO.from_document(previous.response_payload)
            case = _writable_case(uow, command.clinical_case_id)
            original = uow.documentation.get_triage(command.assessment_id)
            current = uow.documentation.current_triage(case.id)
            if original is None or original.clinical_case_id != case.id:
                raise ResourceNotFoundError("triage assessment not found")
            if (
                current is None
                or current.id != original.id
                or original.record_version != command.expected_record_version
            ):
                raise OptimisticConcurrencyError("triage assessment has a newer revision")
            now = utc_now()
            correction = original.corrected(
                assessment_id=command.correction_id,
                source=command.source,
                actor_id=command.actor.actor_id,
                actor_role=command.actor.actor_role,
                occurred_at=command.occurred_at,
                recorded_at=now,
                reason=command.correction_reason,
                context=_context(command.actor),
                **command.content.as_domain_arguments(),
            )
            response = TriageAssessmentDTO(correction)
            uow.documentation.add_triage(correction)
            uow.collect_events([correction])
            _store_idempotency(
                uow,
                command,
                "CorrectTriageAssessment",
                fingerprint,
                correction.id,
                response.to_document(),
                now,
            )
            uow.commit()
            return response


class RecordVitalObservationSetHandler:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def execute(self, command: RecordVitalObservationSet) -> VitalObservationSetDTO:
        payload = {
            "case_id": str(command.clinical_case_id),
            "expected_case_version": command.expected_case_version,
            "observed_at": command.observed_at.isoformat(),
            "source": command.source,
            "content": command.content.fingerprint_document(),
        }
        fingerprint = command_fingerprint(payload)
        with self._unit_of_work() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow,
                command.actor,
                "RecordVitalObservationSet",
                command.idempotency_key,
                fingerprint,
            )
            if previous is not None:
                return VitalObservationSetDTO.from_document(previous.response_payload)
            case = _writable_case(uow, command.clinical_case_id, command.expected_case_version)
            encounter = uow.encounters.get(case.encounter_id)
            if encounter is None:
                raise ResourceNotFoundError("encounter not found")
            now = utc_now()
            vital_set = VitalObservationSet.record(
                vital_set_id=command.vital_set_id,
                clinical_case_id=case.id,
                encounter_id=encounter.id,
                sequence_number=uow.documentation.next_vital_sequence(case.id),
                source=command.source,
                actor_id=command.actor.actor_id,
                actor_role=command.actor.actor_role,
                observed_at=command.observed_at,
                recorded_at=now,
                measurements=command.content.measurements,
                context=_context(command.actor),
                **command.content.as_domain_arguments(),
            )
            response = VitalObservationSetDTO(vital_set)
            uow.documentation.add_vital_set(vital_set)
            uow.collect_events([vital_set])
            _store_idempotency(
                uow,
                command,
                "RecordVitalObservationSet",
                fingerprint,
                vital_set.id,
                response.to_document(),
                now,
            )
            uow.commit()
            return response


class CorrectVitalObservationSetHandler:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def execute(self, command: CorrectVitalObservationSet) -> VitalObservationSetDTO:
        payload = {
            "case_id": str(command.clinical_case_id),
            "vital_set_id": str(command.vital_set_id),
            "expected_record_version": command.expected_record_version,
            "observed_at": command.observed_at.isoformat(),
            "source": command.source,
            "reason": command.correction_reason,
            "content": command.content.fingerprint_document(),
        }
        fingerprint = command_fingerprint(payload)
        with self._unit_of_work() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow,
                command.actor,
                "CorrectVitalObservationSet",
                command.idempotency_key,
                fingerprint,
            )
            if previous is not None:
                return VitalObservationSetDTO.from_document(previous.response_payload)
            case = _writable_case(uow, command.clinical_case_id)
            original = uow.documentation.get_vital_set(command.vital_set_id)
            if original is None or original.clinical_case_id != case.id:
                raise ResourceNotFoundError("vital observation set not found")
            current_revision = max(
                (
                    item.revision_number
                    for item in uow.documentation.vital_history(case.id)
                    if item.sequence_number == original.sequence_number
                ),
                default=0,
            )
            if (
                original.record_version != command.expected_record_version
                or original.revision_number != current_revision
            ):
                raise OptimisticConcurrencyError("vital observation set has a newer revision")
            now = utc_now()
            correction = original.corrected(
                vital_set_id=command.correction_id,
                source=command.source,
                actor_id=command.actor.actor_id,
                actor_role=command.actor.actor_role,
                observed_at=command.observed_at,
                recorded_at=now,
                measurements=command.content.measurements,
                reason=command.correction_reason,
                context=_context(command.actor),
                **command.content.as_domain_arguments(),
            )
            response = VitalObservationSetDTO(correction)
            uow.documentation.add_vital_set(correction)
            uow.collect_events([correction])
            _store_idempotency(
                uow,
                command,
                "CorrectVitalObservationSet",
                fingerprint,
                correction.id,
                response.to_document(),
                now,
            )
            uow.commit()
            return response


class ClinicalDocumentationQueryHandler:
    """Read current/history/summary documentation through repository ports."""

    def __init__(
        self,
        unit_of_work: UnitOfWorkFactory,
        completeness: DocumentationCompletenessPolicy | None = None,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._completeness = completeness or DocumentationCompletenessPolicy()

    def current_triage(self, case_id: UUID) -> TriageAssessment | None:
        with self._unit_of_work() as uow:
            _case(uow, case_id)
            return uow.documentation.current_triage(case_id)

    def triage_history(self, case_id: UUID) -> tuple[TriageAssessment, ...]:
        with self._unit_of_work() as uow:
            _case(uow, case_id)
            return tuple(uow.documentation.triage_history(case_id))

    def vital_history(self, case_id: UUID) -> tuple[VitalObservationSet, ...]:
        with self._unit_of_work() as uow:
            _case(uow, case_id)
            return tuple(uow.documentation.vital_history(case_id))

    def latest_vitals(self, case_id: UUID) -> VitalObservationSet | None:
        with self._unit_of_work() as uow:
            _case(uow, case_id)
            return uow.documentation.latest_vital_set(case_id)

    def summary(self, case_id: UUID) -> TriageVitalsSummaryDTO:
        with self._unit_of_work() as uow:
            case = _case(uow, case_id)
            triage = uow.documentation.current_triage(case_id)
            vitals = uow.documentation.vital_history(case_id)
            latest = vitals[0] if vitals else None
            return TriageVitalsSummaryDTO(
                current_triage=triage,
                latest_vitals=latest,
                recent_vitals=tuple(vitals[:10]),
                missing_documentation=self._completeness.evaluate(triage, latest),
                completeness_policy_version=self._completeness.version,
                data_freshness_at=utc_now(),
                case_version=case.version,
            )


def _validate_actor(uow: ClinicalDocumentationUnitOfWork, actor: ActorContext) -> None:
    if uow.actors.role_for(actor.actor_id) != actor.actor_role:
        raise ActorContextError("verified actor reference is unknown or role does not match")


def _case(uow: ClinicalDocumentationUnitOfWork, case_id: UUID) -> ClinicalCase:
    clinical_case = uow.cases.get(case_id)
    if clinical_case is None:
        raise ResourceNotFoundError("clinical case not found")
    return clinical_case


def _writable_case(
    uow: ClinicalDocumentationUnitOfWork,
    case_id: UUID,
    expected_version: int | None = None,
) -> ClinicalCase:
    clinical_case = _case(uow, case_id)
    if clinical_case.status is CaseStatus.CLOSED:
        raise ResourceConflictError("closed clinical case cannot accept routine documentation")
    if expected_version is not None and clinical_case.version != expected_version:
        raise OptimisticConcurrencyError("clinical case version is stale")
    return clinical_case


def _context(actor: ActorContext) -> EventContext:
    return EventContext(
        correlation_id=actor.correlation_id,
        causation_id=actor.causation_id,
        actor_id=actor.actor_id,
        metadata=actor.audit_metadata(),
    )


def _idempotent(
    uow: ClinicalDocumentationUnitOfWork,
    actor: ActorContext,
    command_type: str,
    key: str,
    fingerprint: str,
) -> IdempotencyResult | None:
    previous = uow.idempotency.lock_and_get(actor.actor_id, command_type, key)
    if previous is not None and previous.request_hash != fingerprint:
        raise IdempotencyConflictError("idempotency key was already used for another payload")
    return previous


def _store_idempotency(
    uow: ClinicalDocumentationUnitOfWork,
    command: RecordTriageAssessment
    | CorrectTriageAssessment
    | RecordVitalObservationSet
    | CorrectVitalObservationSet,
    command_type: str,
    fingerprint: str,
    resource_id: UUID,
    response: dict[str, Any],
    created_at: datetime,
) -> None:
    uow.idempotency.add(
        IdempotencyResult(
            actor_id=command.actor.actor_id,
            command_type=command_type,
            idempotency_key=command.idempotency_key,
            command_id=command.command_id,
            request_hash=fingerprint,
            resource_type=(
                "TriageAssessment" if "Triage" in command_type else "VitalObservationSet"
            ),
            resource_id=resource_id,
            response_payload=response,
            created_at=created_at,
        )
    )


def _triage_document(value: TriageAssessment) -> dict[str, Any]:
    return {
        "id": str(value.id),
        "clinical_case_id": str(value.clinical_case_id),
        "revision_number": value.revision_number,
        "status": value.status.value,
        "source": value.source,
        "recorded_by_actor_id": str(value.recorded_by_actor_id),
        "recorded_by_actor_role": value.recorded_by_actor_role,
        "occurred_at": value.occurred_at.isoformat(),
        "recorded_at": value.recorded_at.isoformat(),
        "correlation_id": str(value.correlation_id),
        "causation_id": str(value.causation_id) if value.causation_id else None,
        "record_version": value.record_version,
        **TriageContent(
            chief_complaint=value.chief_complaint,
            symptom_onset_state=value.symptom_onset_state,
            symptom_onset_at=value.symptom_onset_at,
            symptom_onset_precision=value.symptom_onset_precision,
            symptom_description=value.symptom_description,
            symptom_location=value.symptom_location,
            symptom_radiation=value.symptom_radiation,
            symptom_duration=value.symptom_duration,
            symptom_pattern=value.symptom_pattern,
            aggravating_factors=value.aggravating_factors,
            relieving_factors=value.relieving_factors,
            relevant_history_summary=value.relevant_history_summary,
            current_medication_summary=value.current_medication_summary,
            allergy_summary=value.allergy_summary,
            clinical_note=value.clinical_note,
            associated_symptoms=value.associated_symptoms,
            cardiovascular_risk_factors=value.cardiovascular_risk_factors,
        ).fingerprint_document(),
        "corrects_assessment_id": str(value.corrects_assessment_id)
        if value.corrects_assessment_id
        else None,
        "correction_reason": value.correction_reason,
    }


def _vital_document(value: VitalObservationSet) -> dict[str, Any]:
    return {
        "id": str(value.id),
        "clinical_case_id": str(value.clinical_case_id),
        "encounter_id": str(value.encounter_id),
        "sequence_number": value.sequence_number,
        "revision_number": value.revision_number,
        "source": value.source,
        "device_reference": value.device_reference,
        "recorded_by_actor_id": str(value.recorded_by_actor_id),
        "recorded_by_actor_role": value.recorded_by_actor_role,
        "observed_at": value.observed_at.isoformat(),
        "recorded_at": value.recorded_at.isoformat(),
        "correlation_id": str(value.correlation_id),
        "causation_id": str(value.causation_id) if value.causation_id else None,
        "record_version": value.record_version,
        "measurements": [_measurement_document(item) for item in value.measurements],
        "supplemental_oxygen_state": value.supplemental_oxygen_state.value,
        "oxygen_delivery_method": value.oxygen_delivery_method,
        "level_of_consciousness": value.level_of_consciousness,
        "observation_note": value.observation_note,
        "corrects_vital_set_id": str(value.corrects_vital_set_id)
        if value.corrects_vital_set_id
        else None,
        "correction_reason": value.correction_reason,
    }


def _triage_from_document(value: dict[str, Any]) -> TriageAssessment:
    return TriageAssessment(
        id=UUID(value["id"]),
        clinical_case_id=UUID(value["clinical_case_id"]),
        revision_number=int(value["revision_number"]),
        status=TriageRecordStatus(value["status"]),
        source=value["source"],
        recorded_by_actor_id=UUID(value["recorded_by_actor_id"]),
        recorded_by_actor_role=value["recorded_by_actor_role"],
        occurred_at=datetime.fromisoformat(value["occurred_at"]),
        recorded_at=datetime.fromisoformat(value["recorded_at"]),
        correlation_id=UUID(value["correlation_id"]),
        causation_id=UUID(value["causation_id"]) if value.get("causation_id") else None,
        record_version=int(value["record_version"]),
        chief_complaint=value.get("chief_complaint"),
        symptom_onset_state=ObservationState(value["symptom_onset_state"]),
        symptom_onset_at=datetime.fromisoformat(value["symptom_onset_at"])
        if value.get("symptom_onset_at")
        else None,
        symptom_onset_precision=OnsetPrecision(value["symptom_onset_precision"])
        if value.get("symptom_onset_precision")
        else None,
        symptom_description=value.get("symptom_description"),
        symptom_location=value.get("symptom_location"),
        symptom_radiation=value.get("symptom_radiation"),
        symptom_duration=value.get("symptom_duration"),
        symptom_pattern=value.get("symptom_pattern"),
        aggravating_factors=value.get("aggravating_factors"),
        relieving_factors=value.get("relieving_factors"),
        relevant_history_summary=value.get("relevant_history_summary"),
        current_medication_summary=value.get("current_medication_summary"),
        allergy_summary=value.get("allergy_summary"),
        clinical_note=value.get("clinical_note"),
        associated_symptoms=tuple(
            _structured_from_document(item) for item in value.get("associated_symptoms", [])
        ),
        cardiovascular_risk_factors=tuple(
            _structured_from_document(item) for item in value.get("cardiovascular_risk_factors", [])
        ),
        corrects_assessment_id=UUID(value["corrects_assessment_id"])
        if value.get("corrects_assessment_id")
        else None,
        correction_reason=value.get("correction_reason"),
    )


def _vital_from_document(value: dict[str, Any]) -> VitalObservationSet:
    from vinami.triage.domain.model import DataQualityStatus, VitalKind

    return VitalObservationSet(
        id=UUID(value["id"]),
        clinical_case_id=UUID(value["clinical_case_id"]),
        encounter_id=UUID(value["encounter_id"]),
        sequence_number=int(value["sequence_number"]),
        revision_number=int(value["revision_number"]),
        source=value["source"],
        device_reference=value.get("device_reference"),
        recorded_by_actor_id=UUID(value["recorded_by_actor_id"]),
        recorded_by_actor_role=value["recorded_by_actor_role"],
        observed_at=datetime.fromisoformat(value["observed_at"]),
        recorded_at=datetime.fromisoformat(value["recorded_at"]),
        correlation_id=UUID(value["correlation_id"]),
        causation_id=UUID(value["causation_id"]) if value.get("causation_id") else None,
        record_version=int(value["record_version"]),
        measurements=tuple(
            VitalMeasurement(
                kind=VitalKind(item["kind"]),
                value=float(item["value"]),
                unit=item["unit"],
                source=item["source"],
                observed_at=datetime.fromisoformat(item["observed_at"]),
                quality_status=DataQualityStatus(item["quality_status"]),
            )
            for item in value["measurements"]
        ),
        supplemental_oxygen_state=ObservationState(value["supplemental_oxygen_state"]),
        oxygen_delivery_method=value.get("oxygen_delivery_method"),
        level_of_consciousness=value.get("level_of_consciousness"),
        observation_note=value.get("observation_note"),
        corrects_vital_set_id=UUID(value["corrects_vital_set_id"])
        if value.get("corrects_vital_set_id")
        else None,
        correction_reason=value.get("correction_reason"),
    )


def _measurement_document(value: VitalMeasurement) -> dict[str, object]:
    return {
        "kind": value.kind.value,
        "value": value.value,
        "unit": value.unit,
        "source": value.source,
        "observed_at": value.observed_at.isoformat(),
        "quality_status": value.quality_status.value,
    }


def _structured_observation_document(value: StructuredObservation) -> dict[str, object]:
    return {"name": value.name, "state": value.state.value, "note": value.note}


def _structured_from_document(value: dict[str, Any]) -> StructuredObservation:
    return StructuredObservation(
        name=value["name"], state=ObservationState(value["state"]), note=value.get("note")
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
