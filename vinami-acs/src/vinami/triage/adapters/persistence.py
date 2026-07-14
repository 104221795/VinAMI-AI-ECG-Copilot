"""SQLAlchemy adapter for append-only R2 triage and vital documentation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.shared.persistence import Base, UTCDateTime, UUIDType
from vinami.triage.domain.model import (
    DataQualityStatus,
    ObservationState,
    OnsetPrecision,
    StructuredObservation,
    TriageAssessment,
    TriageRecordStatus,
    VitalKind,
    VitalMeasurement,
    VitalObservationSet,
)


class SymptomObservationRecord(Base):
    """Legacy Sprint 3 mapping retained for additive migration safety only."""

    __tablename__ = "symptom_observations"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)


class VitalObservationRecord(Base):
    """Legacy Sprint 3 mapping retained for additive migration safety only."""

    __tablename__ = "vital_observations"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)


class TriageAssessmentRecord(Base):
    """One immutable triage revision."""

    __tablename__ = "triage_assessments"
    __table_args__ = (
        UniqueConstraint("clinical_case_id", "revision_number", name="uq_triage_case_revision"),
        Index("ix_triage_case_recorded", "clinical_case_id", "recorded_at"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    clinical_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    recorded_by_actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recorded_by_actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptom_onset_state: Mapped[str] = mapped_column(String(40), nullable=False)
    symptom_onset_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    symptom_onset_precision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    symptom_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptom_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptom_radiation: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptom_duration: Mapped[str | None] = mapped_column(String(500), nullable=True)
    symptom_pattern: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    aggravating_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    relieving_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevant_history_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_medication_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergy_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrects_assessment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("triage_assessments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class TriageStructuredObservationRecord(Base):
    """Structured symptom/risk-factor state owned by one triage revision."""

    __tablename__ = "triage_structured_observations"
    __table_args__ = (
        UniqueConstraint(
            "triage_assessment_id", "category", "name", name="uq_triage_observation_name"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    triage_assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("triage_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class VitalObservationSetRecord(Base):
    """One immutable set of co-observed vital measurements."""

    __tablename__ = "vital_observation_sets"
    __table_args__ = (
        UniqueConstraint(
            "clinical_case_id",
            "sequence_number",
            "revision_number",
            name="uq_vital_case_sequence_revision",
        ),
        Index("ix_vital_set_case_observed", "clinical_case_id", "observed_at"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    clinical_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("encounters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    device_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_by_actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recorded_by_actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    supplemental_oxygen_state: Mapped[str] = mapped_column(String(40), nullable=False)
    oxygen_delivery_method: Mapped[str | None] = mapped_column(String(500), nullable=True)
    level_of_consciousness: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    observation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrects_vital_set_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vital_observation_sets.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class VitalMeasurementRecord(Base):
    """One explicit-unit measurement belonging to a vital set revision."""

    __tablename__ = "vital_measurements"
    __table_args__ = (UniqueConstraint("vital_set_id", "kind", name="uq_vital_measurement_kind"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    vital_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("vital_observation_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(40), nullable=False)


class SQLAlchemyClinicalDocumentationRepository:
    """Map append-only documentation aggregates inside the active transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_triage(self, assessment: TriageAssessment) -> None:
        self._session.add(_triage_record(assessment))
        self._session.add_all(
            _structured_records(assessment.id, "associated_symptom", assessment.associated_symptoms)
            + _structured_records(
                assessment.id,
                "cardiovascular_risk_factor",
                assessment.cardiovascular_risk_factors,
            )
        )

    def get_triage(self, assessment_id: UUID) -> TriageAssessment | None:
        record = self._session.get(TriageAssessmentRecord, assessment_id)
        return self._triage_from_record(record) if record is not None else None

    def current_triage(self, case_id: UUID) -> TriageAssessment | None:
        record = self._session.scalar(
            select(TriageAssessmentRecord)
            .where(TriageAssessmentRecord.clinical_case_id == case_id)
            .order_by(TriageAssessmentRecord.revision_number.desc())
            .limit(1)
        )
        return self._triage_from_record(record) if record is not None else None

    def triage_history(self, case_id: UUID) -> list[TriageAssessment]:
        records = self._session.scalars(
            select(TriageAssessmentRecord)
            .where(TriageAssessmentRecord.clinical_case_id == case_id)
            .order_by(TriageAssessmentRecord.revision_number.desc())
        ).all()
        return [self._triage_from_record(record) for record in records]

    def add_vital_set(self, vital_set: VitalObservationSet) -> None:
        parent_record = _vital_set_record(vital_set)
        self._session.add(parent_record)
        self._session.flush([parent_record])
        self._session.add_all(
            VitalMeasurementRecord(
                vital_set_id=vital_set.id,
                kind=measurement.kind.value,
                value=measurement.value,
                unit=measurement.unit,
                source=measurement.source,
                observed_at=measurement.observed_at,
                quality_status=measurement.quality_status.value,
            )
            for measurement in vital_set.measurements
        )

    def get_vital_set(self, vital_set_id: UUID) -> VitalObservationSet | None:
        record = self._session.get(VitalObservationSetRecord, vital_set_id)
        return self._vital_from_record(record) if record is not None else None

    def latest_vital_set(self, case_id: UUID) -> VitalObservationSet | None:
        record = self._session.scalar(
            select(VitalObservationSetRecord)
            .where(VitalObservationSetRecord.clinical_case_id == case_id)
            .order_by(
                VitalObservationSetRecord.sequence_number.desc(),
                VitalObservationSetRecord.revision_number.desc(),
            )
            .limit(1)
        )
        return self._vital_from_record(record) if record is not None else None

    def vital_history(self, case_id: UUID) -> list[VitalObservationSet]:
        records = self._session.scalars(
            select(VitalObservationSetRecord)
            .where(VitalObservationSetRecord.clinical_case_id == case_id)
            .order_by(
                VitalObservationSetRecord.sequence_number.desc(),
                VitalObservationSetRecord.revision_number.desc(),
            )
        ).all()
        return [self._vital_from_record(record) for record in records]

    def next_vital_sequence(self, case_id: UUID) -> int:
        latest = self._session.scalar(
            select(VitalObservationSetRecord.sequence_number)
            .where(VitalObservationSetRecord.clinical_case_id == case_id)
            .order_by(VitalObservationSetRecord.sequence_number.desc())
            .limit(1)
        )
        return (latest or 0) + 1

    def _triage_from_record(self, record: TriageAssessmentRecord) -> TriageAssessment:
        observations = self._session.scalars(
            select(TriageStructuredObservationRecord)
            .where(TriageStructuredObservationRecord.triage_assessment_id == record.id)
            .order_by(
                TriageStructuredObservationRecord.category,
                TriageStructuredObservationRecord.name,
            )
        ).all()
        return TriageAssessment(
            id=record.id,
            clinical_case_id=record.clinical_case_id,
            revision_number=record.revision_number,
            status=TriageRecordStatus(record.status),
            source=record.source,
            recorded_by_actor_id=record.recorded_by_actor_id,
            recorded_by_actor_role=record.recorded_by_actor_role,
            occurred_at=record.occurred_at,
            recorded_at=record.recorded_at,
            correlation_id=record.correlation_id,
            causation_id=record.causation_id,
            record_version=record.record_version,
            chief_complaint=record.chief_complaint,
            symptom_onset_state=ObservationState(record.symptom_onset_state),
            symptom_onset_at=record.symptom_onset_at,
            symptom_onset_precision=(
                OnsetPrecision(record.symptom_onset_precision)
                if record.symptom_onset_precision is not None
                else None
            ),
            symptom_description=record.symptom_description,
            symptom_location=record.symptom_location,
            symptom_radiation=record.symptom_radiation,
            symptom_duration=record.symptom_duration,
            symptom_pattern=record.symptom_pattern,
            aggravating_factors=record.aggravating_factors,
            relieving_factors=record.relieving_factors,
            relevant_history_summary=record.relevant_history_summary,
            current_medication_summary=record.current_medication_summary,
            allergy_summary=record.allergy_summary,
            clinical_note=record.clinical_note,
            associated_symptoms=tuple(
                _structured(observation)
                for observation in observations
                if observation.category == "associated_symptom"
            ),
            cardiovascular_risk_factors=tuple(
                _structured(observation)
                for observation in observations
                if observation.category == "cardiovascular_risk_factor"
            ),
            corrects_assessment_id=record.corrects_assessment_id,
            correction_reason=record.correction_reason,
        )

    def _vital_from_record(self, record: VitalObservationSetRecord) -> VitalObservationSet:
        measurements = self._session.scalars(
            select(VitalMeasurementRecord)
            .where(VitalMeasurementRecord.vital_set_id == record.id)
            .order_by(VitalMeasurementRecord.kind)
        ).all()
        return VitalObservationSet(
            id=record.id,
            clinical_case_id=record.clinical_case_id,
            encounter_id=record.encounter_id,
            sequence_number=record.sequence_number,
            revision_number=record.revision_number,
            source=record.source,
            device_reference=record.device_reference,
            recorded_by_actor_id=record.recorded_by_actor_id,
            recorded_by_actor_role=record.recorded_by_actor_role,
            observed_at=record.observed_at,
            recorded_at=record.recorded_at,
            correlation_id=record.correlation_id,
            causation_id=record.causation_id,
            record_version=record.record_version,
            measurements=tuple(
                VitalMeasurement(
                    kind=VitalKind(item.kind),
                    value=item.value,
                    unit=item.unit,
                    source=item.source,
                    observed_at=item.observed_at,
                    quality_status=DataQualityStatus(item.quality_status),
                )
                for item in measurements
            ),
            supplemental_oxygen_state=ObservationState(record.supplemental_oxygen_state),
            oxygen_delivery_method=record.oxygen_delivery_method,
            level_of_consciousness=record.level_of_consciousness,
            observation_note=record.observation_note,
            corrects_vital_set_id=record.corrects_vital_set_id,
            correction_reason=record.correction_reason,
        )


def _triage_record(value: TriageAssessment) -> TriageAssessmentRecord:
    return TriageAssessmentRecord(
        id=value.id,
        clinical_case_id=value.clinical_case_id,
        revision_number=value.revision_number,
        status=value.status.value,
        source=value.source,
        recorded_by_actor_id=value.recorded_by_actor_id,
        recorded_by_actor_role=value.recorded_by_actor_role,
        occurred_at=value.occurred_at,
        recorded_at=value.recorded_at,
        correlation_id=value.correlation_id,
        causation_id=value.causation_id,
        record_version=value.record_version,
        chief_complaint=value.chief_complaint,
        symptom_onset_state=value.symptom_onset_state.value,
        symptom_onset_at=value.symptom_onset_at,
        symptom_onset_precision=(
            value.symptom_onset_precision.value
            if value.symptom_onset_precision is not None
            else None
        ),
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
        corrects_assessment_id=value.corrects_assessment_id,
        correction_reason=value.correction_reason,
    )


def _vital_set_record(value: VitalObservationSet) -> VitalObservationSetRecord:
    return VitalObservationSetRecord(
        id=value.id,
        clinical_case_id=value.clinical_case_id,
        encounter_id=value.encounter_id,
        sequence_number=value.sequence_number,
        revision_number=value.revision_number,
        source=value.source,
        device_reference=value.device_reference,
        recorded_by_actor_id=value.recorded_by_actor_id,
        recorded_by_actor_role=value.recorded_by_actor_role,
        observed_at=value.observed_at,
        recorded_at=value.recorded_at,
        correlation_id=value.correlation_id,
        causation_id=value.causation_id,
        record_version=value.record_version,
        supplemental_oxygen_state=value.supplemental_oxygen_state.value,
        oxygen_delivery_method=value.oxygen_delivery_method,
        level_of_consciousness=value.level_of_consciousness,
        observation_note=value.observation_note,
        corrects_vital_set_id=value.corrects_vital_set_id,
        correction_reason=value.correction_reason,
    )


def _structured_records(
    assessment_id: UUID, category: str, values: tuple[StructuredObservation, ...]
) -> list[TriageStructuredObservationRecord]:
    return [
        TriageStructuredObservationRecord(
            triage_assessment_id=assessment_id,
            category=category,
            name=value.name,
            state=value.state.value,
            note=value.note,
        )
        for value in values
    ]


def _structured(value: TriageStructuredObservationRecord) -> StructuredObservation:
    return StructuredObservation(
        name=value.name,
        state=ObservationState(value.state),
        note=value.note,
    )
