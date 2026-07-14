"""Framework-free triage and vital documentation aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import TypedDict, Unpack
from uuid import UUID, uuid4

from vinami.shared.domain import AggregateRoot, DomainInvariantError, require_text, require_utc
from vinami.shared.events.contracts import EventContext


class ObservationState(StrEnum):
    """Explicit documentation state; unknown and absence are never equivalent."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"
    NOT_ASSESSED = "not_assessed"


class TriageRecordStatus(StrEnum):
    """How an immutable triage revision entered the record."""

    RECORDED = "recorded"
    CORRECTION = "correction"


class OnsetPrecision(StrEnum):
    """Declared precision of a human-entered symptom-onset timestamp."""

    EXACT = "exact"
    APPROXIMATE = "approximate"
    DATE_ONLY = "date_only"
    UNKNOWN = "unknown"


class VitalKind(StrEnum):
    """Supported factual observations without clinical interpretation."""

    HEART_RATE = "heart_rate"
    SYSTOLIC_BLOOD_PRESSURE = "systolic_blood_pressure"
    DIASTOLIC_BLOOD_PRESSURE = "diastolic_blood_pressure"
    RESPIRATORY_RATE = "respiratory_rate"
    OXYGEN_SATURATION = "oxygen_saturation"
    BODY_TEMPERATURE = "body_temperature"
    PAIN_SCORE = "pain_score"


class DataQualityStatus(StrEnum):
    """Human/device quality declaration, not an inferred physiologic state."""

    ACCEPTED = "accepted"
    QUESTIONABLE = "questionable"
    UNKNOWN = "unknown"


SUPPORTED_UNITS: dict[VitalKind, frozenset[str]] = {
    VitalKind.HEART_RATE: frozenset({"beats/min"}),
    VitalKind.SYSTOLIC_BLOOD_PRESSURE: frozenset({"mmHg"}),
    VitalKind.DIASTOLIC_BLOOD_PRESSURE: frozenset({"mmHg"}),
    VitalKind.RESPIRATORY_RATE: frozenset({"breaths/min"}),
    VitalKind.OXYGEN_SATURATION: frozenset({"%"}),
    VitalKind.BODY_TEMPERATURE: frozenset({"degC"}),
    VitalKind.PAIN_SCORE: frozenset({"score"}),
}


class TriageContentValues(TypedDict, total=False):
    """Typed optional content accepted by triage factories."""

    chief_complaint: str | None
    symptom_onset_state: ObservationState
    symptom_onset_at: datetime | None
    symptom_onset_precision: OnsetPrecision | None
    symptom_description: str | None
    symptom_location: str | None
    symptom_radiation: str | None
    symptom_duration: str | None
    symptom_pattern: str | None
    aggravating_factors: str | None
    relieving_factors: str | None
    relevant_history_summary: str | None
    current_medication_summary: str | None
    allergy_summary: str | None
    clinical_note: str | None
    associated_symptoms: tuple[StructuredObservation, ...]
    cardiovascular_risk_factors: tuple[StructuredObservation, ...]


class VitalContentValues(TypedDict, total=False):
    """Typed optional content accepted by vital-set factories."""

    device_reference: str | None
    supplemental_oxygen_state: ObservationState
    oxygen_delivery_method: str | None
    level_of_consciousness: str | None
    observation_note: str | None


@dataclass(frozen=True, slots=True)
class StructuredObservation:
    """One named symptom or risk-factor fact with explicit uncertainty."""

    name: str
    state: ObservationState
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_text(self.name, "observation name"))
        if self.note is not None:
            object.__setattr__(self, "note", require_text(self.note, "observation note"))


@dataclass(frozen=True, slots=True)
class VitalMeasurement:
    """One unit-bearing numeric observation with its own provenance and time."""

    kind: VitalKind
    value: float
    unit: str
    source: str
    observed_at: datetime
    quality_status: DataQualityStatus = DataQualityStatus.UNKNOWN

    def __post_init__(self) -> None:
        if not isfinite(self.value):
            raise DomainInvariantError("vital value must be finite")
        normalized_unit = require_text(self.unit, "vital unit")
        if normalized_unit not in SUPPORTED_UNITS[self.kind]:
            raise DomainInvariantError(
                f"unsupported unit {normalized_unit!r} for {self.kind.value}"
            )
        object.__setattr__(self, "unit", normalized_unit)
        object.__setattr__(self, "source", require_text(self.source, "vital source"))
        object.__setattr__(self, "observed_at", require_utc(self.observed_at, "observed_at"))


@dataclass(slots=True)
class TriageAssessment(AggregateRoot):
    """One immutable revision of human-entered triage documentation."""

    clinical_case_id: UUID
    revision_number: int
    status: TriageRecordStatus
    source: str
    recorded_by_actor_id: UUID
    recorded_by_actor_role: str
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    record_version: int
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
    corrects_assessment_id: UUID | None = None
    correction_reason: str | None = None

    def __post_init__(self) -> None:
        if self.clinical_case_id.int == 0:
            raise DomainInvariantError("clinical_case_id must not be the nil UUID")
        if self.revision_number < 1 or self.record_version < 1:
            raise DomainInvariantError("triage revision and record version must be positive")
        self.source = require_text(self.source, "triage source")
        self.recorded_by_actor_role = require_text(
            self.recorded_by_actor_role, "recorded_by_actor_role"
        )
        self.occurred_at = require_utc(self.occurred_at, "occurred_at")
        self.recorded_at = require_utc(self.recorded_at, "recorded_at")
        if self.symptom_onset_at is not None:
            self.symptom_onset_at = require_utc(self.symptom_onset_at, "symptom_onset_at")
        if self.symptom_onset_state is ObservationState.PRESENT:
            if self.symptom_onset_at is None or self.symptom_onset_precision is None:
                raise DomainInvariantError(
                    "present symptom onset requires a timestamp and declared precision"
                )
        elif self.symptom_onset_at is not None:
            raise DomainInvariantError(
                "symptom onset timestamp is allowed only when onset is present"
            )
        if self.status is TriageRecordStatus.CORRECTION:
            if self.corrects_assessment_id is None:
                raise DomainInvariantError("triage correction must reference an assessment")
            if self.correction_reason is None:
                raise DomainInvariantError("triage correction requires a reason")
            self.correction_reason = require_text(self.correction_reason, "correction_reason")
        elif self.corrects_assessment_id is not None or self.correction_reason is not None:
            raise DomainInvariantError("recorded triage cannot carry correction metadata")
        for field_name in (
            "chief_complaint",
            "symptom_description",
            "symptom_location",
            "symptom_radiation",
            "symptom_duration",
            "symptom_pattern",
            "aggravating_factors",
            "relieving_factors",
            "relevant_history_summary",
            "current_medication_summary",
            "allergy_summary",
            "clinical_note",
        ):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, require_text(value, field_name))

    @classmethod
    def record(
        cls,
        *,
        assessment_id: UUID | None,
        clinical_case_id: UUID,
        source: str,
        actor_id: UUID,
        actor_role: str,
        occurred_at: datetime,
        recorded_at: datetime,
        context: EventContext,
        **content: Unpack[TriageContentValues],
    ) -> TriageAssessment:
        """Create the first immutable revision and emit its outbox event."""
        assessment = cls(
            id=assessment_id or uuid4(),
            clinical_case_id=clinical_case_id,
            revision_number=1,
            status=TriageRecordStatus.RECORDED,
            source=source,
            recorded_by_actor_id=actor_id,
            recorded_by_actor_role=actor_role,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            record_version=1,
            **content,
        )
        assessment._emit("TriageAssessmentRecorded.v1", context)
        return assessment

    def corrected(
        self,
        *,
        assessment_id: UUID | None,
        source: str,
        actor_id: UUID,
        actor_role: str,
        occurred_at: datetime,
        recorded_at: datetime,
        reason: str,
        context: EventContext,
        **content: Unpack[TriageContentValues],
    ) -> TriageAssessment:
        """Create a new revision while preserving this original record."""
        correction = TriageAssessment(
            id=assessment_id or uuid4(),
            clinical_case_id=self.clinical_case_id,
            revision_number=self.revision_number + 1,
            status=TriageRecordStatus.CORRECTION,
            source=source,
            recorded_by_actor_id=actor_id,
            recorded_by_actor_role=actor_role,
            occurred_at=occurred_at,
            recorded_at=recorded_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            record_version=self.record_version + 1,
            corrects_assessment_id=self.id,
            correction_reason=reason,
            **content,
        )
        correction._emit("TriageAssessmentCorrected.v1", context)
        return correction

    def _emit(self, event_type: str, context: EventContext) -> None:
        payload: dict[str, object] = {
            "case_id": str(self.clinical_case_id),
            "assessment_id": str(self.id),
            "revision_number": self.revision_number,
            "prior_version": self.record_version - 1,
            "resulting_version": self.record_version,
            "source": self.source,
            "recorded_at": self.recorded_at.isoformat(),
        }
        if self.corrects_assessment_id is not None:
            payload["corrects_assessment_id"] = str(self.corrects_assessment_id)
            payload["reason"] = self.correction_reason
        self._record_event(event_type, self.record_version, payload, context)


@dataclass(slots=True)
class VitalObservationSet(AggregateRoot):
    """Observations captured together, retained as immutable revisions."""

    clinical_case_id: UUID
    encounter_id: UUID
    sequence_number: int
    revision_number: int
    source: str
    recorded_by_actor_id: UUID
    recorded_by_actor_role: str
    observed_at: datetime
    recorded_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    record_version: int
    measurements: tuple[VitalMeasurement, ...]
    device_reference: str | None = None
    supplemental_oxygen_state: ObservationState = ObservationState.NOT_ASSESSED
    oxygen_delivery_method: str | None = None
    level_of_consciousness: str | None = None
    observation_note: str | None = None
    corrects_vital_set_id: UUID | None = None
    correction_reason: str | None = None

    def __post_init__(self) -> None:
        if self.clinical_case_id.int == 0 or self.encounter_id.int == 0:
            raise DomainInvariantError("case and encounter identifiers must not be nil")
        if self.sequence_number < 1 or self.revision_number < 1 or self.record_version < 1:
            raise DomainInvariantError("vital sequence, revision, and version must be positive")
        if not self.measurements:
            raise DomainInvariantError("vital observation set requires at least one measurement")
        kinds = [measurement.kind for measurement in self.measurements]
        if len(kinds) != len(set(kinds)):
            raise DomainInvariantError("vital set cannot repeat a measurement kind")
        self.source = require_text(self.source, "vital set source")
        self.recorded_by_actor_role = require_text(
            self.recorded_by_actor_role, "recorded_by_actor_role"
        )
        self.observed_at = require_utc(self.observed_at, "observed_at")
        self.recorded_at = require_utc(self.recorded_at, "recorded_at")
        if self.oxygen_delivery_method is not None:
            self.oxygen_delivery_method = require_text(
                self.oxygen_delivery_method, "oxygen_delivery_method"
            )
        if (
            self.supplemental_oxygen_state is not ObservationState.PRESENT
            and self.oxygen_delivery_method is not None
        ):
            raise DomainInvariantError(
                "oxygen delivery method requires supplemental oxygen to be present"
            )
        for field_name in ("device_reference", "level_of_consciousness", "observation_note"):
            value = getattr(self, field_name)
            if value is not None:
                setattr(self, field_name, require_text(value, field_name))
        if self.corrects_vital_set_id is not None:
            if self.correction_reason is None:
                raise DomainInvariantError("vital correction requires a reason")
            self.correction_reason = require_text(self.correction_reason, "correction_reason")
        elif self.correction_reason is not None:
            raise DomainInvariantError("new vital set cannot carry a correction reason")

    @classmethod
    def record(
        cls,
        *,
        vital_set_id: UUID | None,
        clinical_case_id: UUID,
        encounter_id: UUID,
        sequence_number: int,
        source: str,
        actor_id: UUID,
        actor_role: str,
        observed_at: datetime,
        recorded_at: datetime,
        measurements: tuple[VitalMeasurement, ...],
        context: EventContext,
        **content: Unpack[VitalContentValues],
    ) -> VitalObservationSet:
        """Record a new chronological set and emit its event."""
        vital_set = cls(
            id=vital_set_id or uuid4(),
            clinical_case_id=clinical_case_id,
            encounter_id=encounter_id,
            sequence_number=sequence_number,
            revision_number=1,
            source=source,
            recorded_by_actor_id=actor_id,
            recorded_by_actor_role=actor_role,
            observed_at=observed_at,
            recorded_at=recorded_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            record_version=1,
            measurements=measurements,
            **content,
        )
        vital_set._emit("VitalObservationSetRecorded.v1", context)
        return vital_set

    def corrected(
        self,
        *,
        vital_set_id: UUID | None,
        source: str,
        actor_id: UUID,
        actor_role: str,
        observed_at: datetime,
        recorded_at: datetime,
        measurements: tuple[VitalMeasurement, ...],
        reason: str,
        context: EventContext,
        **content: Unpack[VitalContentValues],
    ) -> VitalObservationSet:
        """Create a correction revision without altering this vital set."""
        correction = VitalObservationSet(
            id=vital_set_id or uuid4(),
            clinical_case_id=self.clinical_case_id,
            encounter_id=self.encounter_id,
            sequence_number=self.sequence_number,
            revision_number=self.revision_number + 1,
            source=source,
            recorded_by_actor_id=actor_id,
            recorded_by_actor_role=actor_role,
            observed_at=observed_at,
            recorded_at=recorded_at,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            record_version=self.record_version + 1,
            measurements=measurements,
            corrects_vital_set_id=self.id,
            correction_reason=reason,
            **content,
        )
        correction._emit("VitalObservationSetCorrected.v1", context)
        return correction

    def _emit(self, event_type: str, context: EventContext) -> None:
        payload: dict[str, object] = {
            "case_id": str(self.clinical_case_id),
            "vital_set_id": str(self.id),
            "sequence_number": self.sequence_number,
            "revision_number": self.revision_number,
            "prior_version": self.record_version - 1,
            "resulting_version": self.record_version,
            "source": self.source,
            "recorded_at": self.recorded_at.isoformat(),
        }
        if self.corrects_vital_set_id is not None:
            payload["corrects_vital_set_id"] = str(self.corrects_vital_set_id)
            payload["reason"] = self.correction_reason
        self._record_event(event_type, self.record_version, payload, context)
