"""R3 PostgreSQL mappings and repository for the complete ECG vertical slice."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

from vinami.ecg.adapters.persistence import ECGStudyRecord
from vinami.ecg.domain.clinical import (
    ComparabilityStatus,
    ComparisonStatus,
    DynamicECGComparison,
    DynamicECGPhysicianReview,
    ECGIngestionJob,
    ECGQualityResult,
    ECGRepeatReminder,
    ECGSourceType,
    ECGWaveform,
    IngestionStatus,
    LeadComparison,
    ModelScoreEvolution,
    ReminderOrigin,
    ReminderStatus,
    SignalFeatureDelta,
    TechnicalQualityStatus,
)
from vinami.ecg.domain.model import ECGQualityAssessment
from vinami.ecg.ports.artifacts import ArtifactMetadata
from vinami.ecg.ports.repository import (
    ECGAnalysisSnapshot,
    ECGFindingSnapshot,
    ECGStudySnapshot,
    PhysicianInterpretationSnapshot,
)
from vinami.shared.domain import OptimisticConcurrencyError
from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class ECGArtifactRecord(Base):
    __tablename__ = "ecg_artifacts"
    __table_args__ = (CheckConstraint("size_bytes > 0", name="ck_ecg_artifact_positive_size"),)
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    artifact_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)


class ECGStudyDetailRecord(Base):
    __tablename__ = "ecg_study_details"
    __table_args__ = (
        UniqueConstraint("study_reference", name="uq_ecg_study_reference"),
        Index("ix_ecg_study_case_acquired", "clinical_case_id", "acquisition_at"),
    )
    study_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="CASCADE"), primary_key=True
    )
    clinical_case_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    encounter_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("encounters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    study_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(240), nullable=False)
    source_connector_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    acquisition_device: Mapped[str | None] = mapped_column(String(500), nullable=True)
    acquisition_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ingestion_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    study_status: Mapped[str] = mapped_column(String(40), nullable=False)
    lead_configuration: Mapped[str] = mapped_column(String(240), nullable=False)
    sampling_rate_hz: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    amplitude_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    raw_artifact_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    normalized_waveform_artifact_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    preview_artifact_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    source_format: Mapped[str] = mapped_column(String(160), nullable=False)
    source_content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_size: Mapped[int] = mapped_column(Integer, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(120), nullable=False)
    preprocessing_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_actor_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    waveform_available: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ECGWaveformMetadataRecord(Base):
    __tablename__ = "ecg_waveform_metadata"
    study_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="CASCADE"), primary_key=True
    )
    document: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False)


class ECGQualityRecord(Base):
    __tablename__ = "ecg_quality_assessments"
    __table_args__ = (
        UniqueConstraint("study_id"),
        Index("ix_ecg_quality_assessments_study_id", "study_id"),
    )
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    study_id: Mapped[UUID] = mapped_column(
        UUIDType,
        ForeignKey("ecg_studies.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    affected_leads: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    parser_warnings: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    preprocessing_warnings: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(120), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class ECGIngestionJobRecord(Base):
    __tablename__ = "ecg_ingestion_jobs"
    __table_args__ = (Index("ix_ecg_ingestion_case_requested", "clinical_case_id", "requested_at"),)
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    clinical_case_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_connector_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_by: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_role: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    request_source: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    study_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    acquisition_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    artifact_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    resulting_study_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="RESTRICT"), nullable=True
    )
    parser_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    failure_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_detail_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_of_job_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_ingestion_jobs.id", ondelete="RESTRICT"), nullable=True
    )
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)


class ECGAIAnalysisRecord(Base):
    __tablename__ = "ecg_ai_analyses"
    __table_args__ = (Index("ix_ecg_analysis_study_requested", "ecg_study_id", "requested_at"),)
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    ecg_study_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="CASCADE"), nullable=False
    )
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    model_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preprocessing_version: Mapped[str] = mapped_column(String(120), nullable=False)
    label_mapping_version: Mapped[str] = mapped_column(String(120), nullable=False)
    threshold_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    input_artifact_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    input_artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quality_status: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    inference_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    explanation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation_artifact_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    failure_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_detail_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ECGAIAnalysisFindingRecord(Base):
    __tablename__ = "ecg_ai_analysis_findings"
    __table_args__ = (
        UniqueConstraint("analysis_id", "finding_code", name="uq_ecg_analysis_finding"),
    )
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_ai_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_code: Mapped[str] = mapped_column(String(80), nullable=False)
    display_label: Mapped[str] = mapped_column(String(240), nullable=False)
    model_score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_met: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_status: Mapped[str] = mapped_column(String(80), nullable=False)
    explanation_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PhysicianECGInterpretationRecord(Base):
    __tablename__ = "physician_ecg_interpretations"
    __table_args__ = (
        UniqueConstraint("ecg_study_id", "revision_number", name="uq_ecg_interpretation_revision"),
    )
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    ecg_study_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_ai_analyses.id", ondelete="RESTRICT"), nullable=True
    )
    actor_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    interpretation_status: Mapped[str] = mapped_column(String(80), nullable=False)
    structured_interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    agreement_status: Mapped[str] = mapped_column(String(80), nullable=False)
    disagreement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_disposition: Mapped[str] = mapped_column(String(80), nullable=False)
    repeat_ecg_requested: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_interpretation_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("physician_ecg_interpretations.id", ondelete="RESTRICT"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DynamicECGComparisonRecord(Base):
    __tablename__ = "dynamic_ecg_comparisons"
    __table_args__ = (
        CheckConstraint(
            "baseline_study_id <> current_study_id", name="ck_dynamic_ecg_distinct_studies"
        ),
        Index("ix_dynamic_ecg_case_requested", "clinical_case_id", "requested_at"),
    )
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    clinical_case_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    baseline_study_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="RESTRICT"), nullable=False
    )
    current_study_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="RESTRICT"), nullable=False
    )
    comparison_policy_version: Mapped[str] = mapped_column(String(120), nullable=False)
    preprocessing_version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    comparability_status: Mapped[str] = mapped_column(String(40), nullable=False)
    comparability_reasons: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    lead_comparisons: Mapped[list[dict[str, object]]] = mapped_column(JSONDocument, nullable=False)
    technical_change_indicators: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    signal_feature_deltas: Mapped[list[dict[str, object]]] = mapped_column(
        JSONDocument, nullable=False, default=list
    )
    rhythm_change_indicators: Mapped[list[str]] = mapped_column(
        JSONDocument, nullable=False, default=list
    )
    st_t_change_indicators: Mapped[list[str]] = mapped_column(
        JSONDocument, nullable=False, default=list
    )
    model_score_deltas: Mapped[list[dict[str, object]]] = mapped_column(
        JSONDocument, nullable=False
    )
    quality_context: Mapped[str] = mapped_column(Text, nullable=False)
    review_recommendation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Technical serial ECG comparison only; physician interpretation is required.",
    )
    requested_by: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_role: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    physician_review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    model_score_compatibility: Mapped[str] = mapped_column(String(80), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)


class DynamicECGPhysicianReviewRecord(Base):
    __tablename__ = "dynamic_ecg_physician_reviews"
    __table_args__ = (
        UniqueConstraint("comparison_id", "revision_number", name="uq_dynamic_review_revision"),
    )
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    comparison_id: Mapped[UUID] = mapped_column(
        UUIDType,
        ForeignKey("dynamic_ecg_comparisons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    review_status: Mapped[str] = mapped_column(String(80), nullable=False)
    interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_review_id: Mapped[UUID | None] = mapped_column(
        UUIDType,
        ForeignKey("dynamic_ecg_physician_reviews.id", ondelete="RESTRICT"),
        nullable=True,
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ECGRepeatReminderRecord(Base):
    __tablename__ = "ecg_repeat_reminders"
    __table_args__ = (Index("ix_ecg_repeat_case_due", "clinical_case_id", "due_at"),)
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    clinical_case_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    source_study_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_role: Mapped[str] = mapped_column(String(80), nullable=False)
    origin: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_study_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("ecg_studies.id", ondelete="RESTRICT"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancelled_by: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)


class SQLAlchemyECGClinicalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_artifact(self, value: ArtifactMetadata) -> None:
        record = ECGArtifactRecord(
            id=value.artifact_id,
            artifact_kind=value.artifact_kind,
            content_type=value.content_type,
            size_bytes=value.size_bytes,
            checksum_sha256=value.checksum_sha256,
            state=value.state,
            original_filename=value.original_filename,
            created_at=value.created_at,
        )
        self._session.add(record)
        # Artifact consumers intentionally have no ORM relationships. Make the
        # immutable metadata parent visible before dependent rows are flushed.
        self._session.flush([record])

    def get_artifact(self, artifact_id: UUID) -> ArtifactMetadata | None:
        value = self._session.get(ECGArtifactRecord, artifact_id)
        return (
            None
            if value is None
            else ArtifactMetadata(
                value.id,
                value.artifact_kind,
                value.content_type,
                value.size_bytes,
                value.checksum_sha256,
                value.state,
                value.created_at,
                value.original_filename,
            )
        )

    def add_ingestion_job(self, value: ECGIngestionJob) -> None:
        self._session.add(_job_record(value))

    def get_ingestion_job(self, job_id: UUID) -> ECGIngestionJob | None:
        value = self._session.get(ECGIngestionJobRecord, job_id)
        return _job_domain(value) if value else None

    def save_ingestion_job(self, value: ECGIngestionJob) -> None:
        record = self._session.get(ECGIngestionJobRecord, value.id)
        if record is None:
            raise ValueError("ECG ingestion job does not exist")
        for name in (
            "status",
            "started_at",
            "completed_at",
            "artifact_id",
            "resulting_study_id",
            "parser_name",
            "parser_version",
            "failure_category",
            "failure_detail_safe",
            "retry_count",
            "retry_of_job_id",
            "record_version",
        ):
            item = getattr(value, name)
            setattr(record, name, item.value if hasattr(item, "value") else item)
        record.warnings = list(value.warnings)

    def list_ingestion_jobs(self, case_id: UUID) -> tuple[ECGIngestionJob, ...]:
        values = self._session.scalars(
            select(ECGIngestionJobRecord)
            .where(ECGIngestionJobRecord.clinical_case_id == case_id)
            .order_by(ECGIngestionJobRecord.requested_at.desc(), ECGIngestionJobRecord.id)
        ).all()
        return tuple(_job_domain(value) for value in values)

    def add_study(
        self, value: ECGStudySnapshot, waveform: ECGWaveform | None, quality: ECGQualityResult
    ) -> None:
        self._session.add(
            ECGStudyRecord(
                id=value.study_id,
                case_id=value.clinical_case_id,
                input_reference=f"artifact://{value.raw_artifact_id}",
                content_checksum=value.artifact_checksum,
                media_type=value.source_content_type,
                acquisition_metadata={
                    "source_system": value.source_system,
                    "source_record_id": value.study_reference,
                    "input_format": value.source_format,
                    "lead_configuration": value.lead_configuration,
                    "sampling_hz": int(value.sampling_rate_hz) if value.sampling_rate_hz else None,
                    "lead_count": len(waveform.lead_names) if waveform else None,
                    "acquired_at": value.acquisition_at.isoformat(),
                    "device_name": value.acquisition_device,
                },
                uploaded_at=value.ingestion_at,
                quality=_legacy_quality(quality.status),
                quality_note=",".join(quality.reason_codes) or "technical quality assessed",
            )
        )
        self._session.add(
            ECGStudyDetailRecord(
                **{field: getattr(value, field) for field in ECGStudySnapshot.__dataclass_fields__}
            )
        )
        if waveform:
            self._session.add(
                ECGWaveformMetadataRecord(
                    study_id=value.study_id, document=_waveform_document(waveform)
                )
            )
        self._session.add(
            ECGQualityRecord(
                study_id=value.study_id,
                status=quality.status.value,
                reason_codes=list(quality.reason_codes),
                affected_leads=list(quality.affected_leads),
                parser_warnings=list(quality.parser_warnings),
                preprocessing_warnings=list(quality.preprocessing_warnings),
                engine_version=quality.engine_version,
                assessed_at=quality.assessed_at,
            )
        )

    def get_study(self, study_id: UUID) -> ECGStudySnapshot | None:
        value = self._session.get(ECGStudyDetailRecord, study_id)
        return _study_snapshot(value) if value else None

    def list_studies(self, case_id: UUID) -> tuple[ECGStudySnapshot, ...]:
        values = self._session.scalars(
            select(ECGStudyDetailRecord)
            .where(ECGStudyDetailRecord.clinical_case_id == case_id)
            .order_by(ECGStudyDetailRecord.acquisition_at, ECGStudyDetailRecord.study_id)
        ).all()
        return tuple(_study_snapshot(value) for value in values)

    def get_waveform(self, study_id: UUID) -> ECGWaveform | None:
        value = self._session.get(ECGWaveformMetadataRecord, study_id)
        return _waveform_domain(value.document) if value else None

    def get_quality(self, study_id: UUID) -> ECGQualityResult | None:
        value = self._session.scalar(
            select(ECGQualityRecord).where(ECGQualityRecord.study_id == study_id)
        )
        return (
            None
            if value is None
            else ECGQualityResult(
                TechnicalQualityStatus(value.status),
                tuple(value.reason_codes),
                tuple(value.affected_leads),
                tuple(value.parser_warnings),
                tuple(value.preprocessing_warnings),
                value.engine_version,
                value.assessed_at,
            )
        )

    def add_analysis(self, value: ECGAnalysisSnapshot) -> None:
        data = {
            field: getattr(value, field)
            for field in ECGAnalysisSnapshot.__dataclass_fields__
            if field not in {"analysis_id", "findings"}
        }
        self._session.add(ECGAIAnalysisRecord(id=value.analysis_id, **data))
        # Findings intentionally have no ORM relationship. Flush the parent
        # inside this transaction before staging rows that reference it.
        self._session.flush()
        self._session.add_all(
            [
                ECGAIAnalysisFindingRecord(analysis_id=value.analysis_id, **asdict(finding))
                for finding in value.findings
            ]
        )

    def get_analysis(self, analysis_id: UUID) -> ECGAnalysisSnapshot | None:
        value = self._session.get(ECGAIAnalysisRecord, analysis_id)
        return _analysis_snapshot(value, self._findings(analysis_id)) if value else None

    def list_analyses(self, study_id: UUID) -> tuple[ECGAnalysisSnapshot, ...]:
        values = self._session.scalars(
            select(ECGAIAnalysisRecord)
            .where(ECGAIAnalysisRecord.ecg_study_id == study_id)
            .order_by(ECGAIAnalysisRecord.requested_at.desc(), ECGAIAnalysisRecord.id.desc())
        ).all()
        return tuple(_analysis_snapshot(value, self._findings(value.id)) for value in values)

    def _findings(self, analysis_id: UUID) -> tuple[ECGFindingSnapshot, ...]:
        values = self._session.scalars(
            select(ECGAIAnalysisFindingRecord)
            .where(ECGAIAnalysisFindingRecord.analysis_id == analysis_id)
            .order_by(ECGAIAnalysisFindingRecord.rank)
        ).all()
        return tuple(
            ECGFindingSnapshot(
                finding_code=value.finding_code,
                display_label=value.display_label,
                model_score=value.model_score,
                threshold=value.threshold,
                threshold_met=value.threshold_met,
                rank=value.rank,
                finding_status=value.finding_status,
                explanation_reference=value.explanation_reference,
            )
            for value in values
        )

    def add_interpretation(self, value: PhysicianInterpretationSnapshot) -> None:
        self._session.add(
            PhysicianECGInterpretationRecord(
                id=value.interpretation_id,
                **{
                    field: getattr(value, field)
                    for field in PhysicianInterpretationSnapshot.__dataclass_fields__
                    if field != "interpretation_id"
                },
            )
        )

    def get_interpretation(self, interpretation_id: UUID) -> PhysicianInterpretationSnapshot | None:
        value = self._session.get(PhysicianECGInterpretationRecord, interpretation_id)
        return _interpretation_snapshot(value) if value else None

    def list_interpretations(self, study_id: UUID) -> tuple[PhysicianInterpretationSnapshot, ...]:
        values = self._session.scalars(
            select(PhysicianECGInterpretationRecord)
            .where(PhysicianECGInterpretationRecord.ecg_study_id == study_id)
            .order_by(PhysicianECGInterpretationRecord.revision_number.desc())
        ).all()
        return tuple(_interpretation_snapshot(value) for value in values)

    def add_comparison(self, value: DynamicECGComparison) -> None:
        self._session.add(
            DynamicECGComparisonRecord(
                id=value.id,
                clinical_case_id=value.clinical_case_id,
                baseline_study_id=value.baseline_study_id,
                current_study_id=value.current_study_id,
                comparison_policy_version=value.comparison_policy_version,
                preprocessing_version=value.preprocessing_version,
                status=value.status.value,
                comparability_status=value.comparability_status.value,
                comparability_reasons=list(value.comparability_reasons),
                lead_comparisons=[_lead_document(item) for item in value.lead_comparisons],
                technical_change_indicators=list(value.technical_change_indicators),
                signal_feature_deltas=[asdict(item) for item in value.signal_feature_deltas],
                rhythm_change_indicators=list(value.rhythm_change_indicators),
                st_t_change_indicators=list(value.st_t_change_indicators),
                model_score_deltas=[asdict(item) for item in value.model_score_deltas],
                quality_context=value.quality_context,
                review_recommendation=value.review_recommendation,
                requested_by=value.requested_by,
                requested_by_role=value.requested_by_role,
                requested_at=value.requested_at,
                started_at=value.started_at,
                completed_at=value.completed_at,
                physician_review_status=value.physician_review_status,
                model_score_compatibility=value.model_score_compatibility,
                correlation_id=value.correlation_id,
                record_version=value.record_version,
            )
        )

    def get_comparison(self, comparison_id: UUID) -> DynamicECGComparison | None:
        value = self._session.get(DynamicECGComparisonRecord, comparison_id)
        return _comparison_domain(value) if value else None

    def list_comparisons(self, case_id: UUID) -> tuple[DynamicECGComparison, ...]:
        values = self._session.scalars(
            select(DynamicECGComparisonRecord)
            .where(DynamicECGComparisonRecord.clinical_case_id == case_id)
            .order_by(DynamicECGComparisonRecord.requested_at.desc())
        ).all()
        return tuple(_comparison_domain(value) for value in values)

    def add_comparison_review(self, value: DynamicECGPhysicianReview) -> None:
        self._session.add(
            DynamicECGPhysicianReviewRecord(
                id=value.review_id,
                **{
                    field: getattr(value, field)
                    for field in DynamicECGPhysicianReview.__dataclass_fields__
                    if field != "review_id"
                },
            )
        )

    def get_comparison_review(self, review_id: UUID) -> DynamicECGPhysicianReview | None:
        value = self._session.get(DynamicECGPhysicianReviewRecord, review_id)
        return _comparison_review_domain(value) if value else None

    def list_comparison_reviews(self, comparison_id: UUID) -> tuple[DynamicECGPhysicianReview, ...]:
        values = self._session.scalars(
            select(DynamicECGPhysicianReviewRecord)
            .where(DynamicECGPhysicianReviewRecord.comparison_id == comparison_id)
            .order_by(DynamicECGPhysicianReviewRecord.revision_number.desc())
        ).all()
        return tuple(_comparison_review_domain(value) for value in values)

    def add_reminder(self, value: ECGRepeatReminder) -> None:
        self._session.add(_reminder_record(value))

    def get_reminder(self, reminder_id: UUID) -> ECGRepeatReminder | None:
        value = self._session.get(ECGRepeatReminderRecord, reminder_id)
        return _reminder_domain(value) if value else None

    def save_reminder(self, value: ECGRepeatReminder, expected_version: int) -> None:
        record = self._session.get(ECGRepeatReminderRecord, value.id)
        if record is None:
            raise ValueError("repeat ECG reminder does not exist")
        if record.record_version != expected_version:
            raise OptimisticConcurrencyError("repeat ECG reminder has a newer version")
        record.status = value.status.value
        record.acknowledged_by = value.acknowledged_by
        record.acknowledged_at = value.acknowledged_at
        record.completed_study_id = value.completed_study_id
        record.completed_at = value.completed_at
        record.cancelled_by = value.cancelled_by
        record.cancelled_at = value.cancelled_at
        record.cancellation_reason = value.cancellation_reason
        record.updated_at = value.updated_at or value.created_at
        record.record_version = value.record_version

    def list_reminders(self, case_id: UUID) -> tuple[ECGRepeatReminder, ...]:
        values = self._session.scalars(
            select(ECGRepeatReminderRecord)
            .where(ECGRepeatReminderRecord.clinical_case_id == case_id)
            .order_by(ECGRepeatReminderRecord.due_at.desc())
        ).all()
        return tuple(_reminder_domain(value) for value in values)


def _legacy_quality(value: TechnicalQualityStatus) -> ECGQualityAssessment:
    return {
        TechnicalQualityStatus.ACCEPTABLE: ECGQualityAssessment.ACCEPTABLE,
        TechnicalQualityStatus.LIMITED: ECGQualityAssessment.LIMITED,
    }.get(value, ECGQualityAssessment.UNUSABLE)


def _job_record(value: ECGIngestionJob) -> ECGIngestionJobRecord:
    return ECGIngestionJobRecord(
        id=value.id,
        clinical_case_id=value.clinical_case_id,
        source_type=value.source_type.value,
        source_connector_id=value.source_connector_id,
        external_reference=value.external_reference,
        status=value.status.value,
        requested_by=value.requested_by,
        requested_by_role=value.requested_by_role,
        requested_at=value.requested_at,
        request_source=value.request_source,
        idempotency_key=value.idempotency_key,
        study_reference=value.study_reference,
        acquisition_at=value.acquisition_at,
        content_type=value.content_type,
        started_at=value.started_at,
        completed_at=value.completed_at,
        artifact_id=value.artifact_id,
        resulting_study_id=value.resulting_study_id,
        parser_name=value.parser_name,
        parser_version=value.parser_version,
        warnings=list(value.warnings),
        failure_category=value.failure_category,
        failure_detail_safe=value.failure_detail_safe,
        retry_count=value.retry_count,
        retry_of_job_id=value.retry_of_job_id,
        correlation_id=value.correlation_id,
        record_version=value.record_version,
    )


def _job_domain(value: ECGIngestionJobRecord) -> ECGIngestionJob:
    return ECGIngestionJob(
        id=value.id,
        clinical_case_id=value.clinical_case_id,
        source_type=ECGSourceType(value.source_type),
        status=IngestionStatus(value.status),
        requested_by=value.requested_by,
        requested_by_role=value.requested_by_role,
        requested_at=value.requested_at,
        correlation_id=value.correlation_id,
        request_source=value.request_source,
        idempotency_key=value.idempotency_key,
        study_reference=value.study_reference,
        acquisition_at=value.acquisition_at,
        content_type=value.content_type,
        record_version=value.record_version,
        source_connector_id=value.source_connector_id,
        external_reference=value.external_reference,
        artifact_id=value.artifact_id,
        resulting_study_id=value.resulting_study_id,
        parser_name=value.parser_name,
        parser_version=value.parser_version,
        warnings=tuple(value.warnings),
        failure_category=value.failure_category,
        failure_detail_safe=value.failure_detail_safe,
        retry_count=value.retry_count,
        retry_of_job_id=value.retry_of_job_id,
        started_at=value.started_at,
        completed_at=value.completed_at,
    )


def _study_snapshot(value: ECGStudyDetailRecord) -> ECGStudySnapshot:
    data = {
        field: getattr(value, field)
        for field in ECGStudySnapshot.__dataclass_fields__
        if field != "source_type"
    }
    return ECGStudySnapshot(
        source_type=ECGSourceType(value.source_type),
        **data,
    )


def _waveform_document(value: ECGWaveform) -> dict[str, object]:
    return {
        "study_reference": value.study_reference,
        "lead_names": list(value.lead_names),
        "samples_per_lead": value.samples_per_lead,
        "sampling_rate_hz": value.sampling_rate_hz,
        "duration_seconds": value.duration_seconds,
        "original_amplitude_unit": value.original_amplitude_unit,
        "normalized_amplitude_unit": value.normalized_amplitude_unit,
        "time_unit": value.time_unit,
        "acquisition_at": value.acquisition_at.isoformat(),
        "source_format": value.source_format,
        "source_device": value.source_device,
        "missing_leads": list(value.missing_leads),
        "parser_warnings": list(value.parser_warnings),
        "preprocessing_version": value.preprocessing_version,
        "checksum": value.checksum,
        "conversion_method": value.conversion_method,
        "conversion_version": value.conversion_version,
        "calibration": value.calibration,
        "source_identifiers": [list(item) for item in value.source_identifiers],
    }


def _waveform_domain(value: dict[str, object]) -> ECGWaveform:
    return ECGWaveform(
        study_reference=str(value["study_reference"]),
        lead_names=_string_tuple(value["lead_names"], "lead_names"),
        samples_per_lead=_integer(value["samples_per_lead"], "samples_per_lead"),
        sampling_rate_hz=_number(value["sampling_rate_hz"], "sampling_rate_hz"),
        duration_seconds=_number(value["duration_seconds"], "duration_seconds"),
        original_amplitude_unit=str(value["original_amplitude_unit"]),
        normalized_amplitude_unit=str(value["normalized_amplitude_unit"]),
        time_unit=str(value["time_unit"]),
        acquisition_at=datetime.fromisoformat(str(value["acquisition_at"])),
        source_format=str(value["source_format"]),
        source_device=str(value["source_device"]) if value.get("source_device") else None,
        missing_leads=_string_tuple(value["missing_leads"], "missing_leads"),
        parser_warnings=_string_tuple(value["parser_warnings"], "parser_warnings"),
        preprocessing_version=str(value["preprocessing_version"]),
        checksum=str(value["checksum"]),
        conversion_method=str(value["conversion_method"])
        if value.get("conversion_method")
        else None,
        conversion_version=str(value["conversion_version"])
        if value.get("conversion_version")
        else None,
        calibration=str(value["calibration"]) if value.get("calibration") else None,
        source_identifiers=_identifier_pairs(value.get("source_identifiers")),
    )


def _analysis_snapshot(
    value: ECGAIAnalysisRecord, findings: tuple[ECGFindingSnapshot, ...]
) -> ECGAnalysisSnapshot:
    data = {
        field: getattr(value, field)
        for field in ECGAnalysisSnapshot.__dataclass_fields__
        if field != "analysis_id" and field != "findings"
    }
    data["warnings"] = tuple(value.warnings)
    return ECGAnalysisSnapshot(analysis_id=value.id, findings=findings, **data)


def _interpretation_snapshot(
    value: PhysicianECGInterpretationRecord,
) -> PhysicianInterpretationSnapshot:
    return PhysicianInterpretationSnapshot(
        interpretation_id=value.id,
        **{
            field: getattr(value, field)
            for field in PhysicianInterpretationSnapshot.__dataclass_fields__
            if field != "interpretation_id"
        },
    )


def _lead_document(value: LeadComparison) -> dict[str, object]:
    return asdict(value)


def _lead_domain(value: dict[str, object]) -> LeadComparison:
    return LeadComparison(
        lead_name=str(value["lead_name"]),
        waveform_similarity=_number(value["waveform_similarity"], "waveform_similarity"),
        normalized_difference=_number(value["normalized_difference"], "normalized_difference"),
        amplitude_scale_change=_number(value["amplitude_scale_change"], "amplitude_scale_change"),
        baseline_shift_indicator=_number(
            value["baseline_shift_indicator"], "baseline_shift_indicator"
        ),
        missing_data_percentage=_number(
            value["missing_data_percentage"], "missing_data_percentage"
        ),
        quality_difference=str(value["quality_difference"]),
        sample_alignment_status=str(value.get("sample_alignment_status", "aligned")),
    )


def _score_delta(value: dict[str, object]) -> ModelScoreEvolution:
    return ModelScoreEvolution(
        finding_code=str(value["finding_code"]),
        previous_score=_number(value["previous_score"], "previous_score"),
        current_score=_number(value["current_score"], "current_score"),
        absolute_delta=_number(value["absolute_delta"], "absolute_delta"),
        previous_threshold_met=_optional_bool(value.get("previous_threshold_met")),
        current_threshold_met=_optional_bool(value.get("current_threshold_met")),
        threshold_state_changed=_optional_bool(value.get("threshold_state_changed")),
        previous_model_version=str(value["previous_model_version"]),
        current_model_version=str(value["current_model_version"]),
        compatibility_status=str(value["compatibility_status"]),
    )


def _signal_feature_delta(value: dict[str, object]) -> SignalFeatureDelta:
    return SignalFeatureDelta(
        feature_name=str(value["feature_name"]),
        display_label=str(value["display_label"]),
        previous_value=_optional_number(value.get("previous_value"), "previous_value"),
        current_value=_optional_number(value.get("current_value"), "current_value"),
        absolute_delta=_optional_number(value.get("absolute_delta"), "absolute_delta"),
        unit=str(value["unit"]) if value.get("unit") is not None else None,
        status=str(value["status"]),
        evidence_scope=str(value["evidence_scope"]),
    )


def _comparison_domain(value: DynamicECGComparisonRecord) -> DynamicECGComparison:
    return DynamicECGComparison(
        id=value.id,
        clinical_case_id=value.clinical_case_id,
        baseline_study_id=value.baseline_study_id,
        current_study_id=value.current_study_id,
        comparison_policy_version=value.comparison_policy_version,
        preprocessing_version=value.preprocessing_version,
        status=ComparisonStatus(value.status),
        comparability_status=ComparabilityStatus(value.comparability_status),
        comparability_reasons=tuple(value.comparability_reasons),
        lead_comparisons=tuple(_lead_domain(item) for item in value.lead_comparisons),
        technical_change_indicators=tuple(value.technical_change_indicators),
        signal_feature_deltas=tuple(
            _signal_feature_delta(item) for item in value.signal_feature_deltas
        ),
        rhythm_change_indicators=tuple(value.rhythm_change_indicators),
        st_t_change_indicators=tuple(value.st_t_change_indicators),
        model_score_deltas=tuple(_score_delta(item) for item in value.model_score_deltas),
        quality_context=value.quality_context,
        review_recommendation=value.review_recommendation,
        requested_by=value.requested_by,
        requested_by_role=value.requested_by_role,
        requested_at=value.requested_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        physician_review_status=value.physician_review_status,
        model_score_compatibility=value.model_score_compatibility,
        correlation_id=value.correlation_id,
        record_version=value.record_version,
    )


def _comparison_review_domain(
    value: DynamicECGPhysicianReviewRecord,
) -> DynamicECGPhysicianReview:
    return DynamicECGPhysicianReview(
        review_id=value.id,
        comparison_id=value.comparison_id,
        actor_id=value.actor_id,
        actor_role=value.actor_role,
        review_status=value.review_status,
        interpretation=value.interpretation,
        occurred_at=value.occurred_at,
        recorded_at=value.recorded_at,
        correlation_id=value.correlation_id,
        record_version=value.record_version,
        revision_number=value.revision_number,
        supersedes_review_id=value.supersedes_review_id,
        correction_reason=value.correction_reason,
    )


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"persisted ECG {field} is malformed")
    return tuple(str(item) for item in value)


def _identifier_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        (str(item[0]), str(item[1])) for item in value if isinstance(item, list) and len(item) == 2
    )


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"persisted ECG {field} is malformed")
    return float(value)


def _optional_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    return _number(value, field)


def _integer(value: object, field: str) -> int:
    number = _number(value, field)
    if not number.is_integer():
        raise ValueError(f"persisted ECG {field} must be an integer")
    return int(number)


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _reminder_record(value: ECGRepeatReminder) -> ECGRepeatReminderRecord:
    return ECGRepeatReminderRecord(
        id=value.id,
        clinical_case_id=value.clinical_case_id,
        source_study_id=value.source_study_id,
        requested_by=value.requested_by,
        requested_by_role=value.requested_by_role,
        origin=value.origin.value,
        reason=value.reason,
        due_at=value.due_at,
        status=value.status.value,
        acknowledged_by=value.acknowledged_by,
        acknowledged_at=value.acknowledged_at,
        completed_study_id=value.completed_study_id,
        completed_at=value.completed_at,
        cancelled_by=value.cancelled_by,
        cancelled_at=value.cancelled_at,
        cancellation_reason=value.cancellation_reason,
        created_at=value.created_at,
        updated_at=value.updated_at or value.created_at,
        correlation_id=value.correlation_id,
        record_version=value.record_version,
    )


def _reminder_domain(value: ECGRepeatReminderRecord) -> ECGRepeatReminder:
    return ECGRepeatReminder(
        id=value.id,
        clinical_case_id=value.clinical_case_id,
        source_study_id=value.source_study_id,
        requested_by=value.requested_by,
        requested_by_role=value.requested_by_role,
        origin=ReminderOrigin(value.origin),
        reason=value.reason,
        due_at=value.due_at,
        status=ReminderStatus(value.status),
        acknowledged_by=value.acknowledged_by,
        acknowledged_at=value.acknowledged_at,
        completed_study_id=value.completed_study_id,
        completed_at=value.completed_at,
        cancelled_by=value.cancelled_by,
        cancelled_at=value.cancelled_at,
        cancellation_reason=value.cancellation_reason,
        created_at=value.created_at,
        updated_at=value.updated_at,
        correlation_id=value.correlation_id,
        record_version=value.record_version,
    )
