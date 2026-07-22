"""R3 ECG clinical-product domain contracts without framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import AggregateRoot, DomainInvariantError, require_text, require_utc
from vinami.shared.events.contracts import EventContext

STANDARD_12_LEADS = ("I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6")
BLOCKING_QUALITY = frozenset({"poor", "insufficient", "unsupported", "failed"})


class ECGSourceType(StrEnum):
    MANUAL_UPLOAD = "manual_upload"
    CANONICAL_WAVEFORM = "canonical_waveform"
    DICOM_FILE = "dicom_file"
    DICOM_CONNECTOR = "dicom_connector"
    VENDOR_XML = "vendor_xml"
    PDF_DOCUMENT = "pdf_document"
    SEEDED_DEMO = "seeded_demo"
    UNKNOWN = "unknown"


class IngestionStatus(StrEnum):
    REQUESTED = "requested"
    RECEIVING = "receiving"
    VALIDATING = "validating"
    PARSING = "parsing"
    NORMALIZING = "normalizing"
    ASSESSING_QUALITY = "assessing_quality"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class TechnicalQualityStatus(StrEnum):
    PENDING = "pending"
    ACCEPTABLE = "acceptable"
    LIMITED = "limited"
    POOR = "poor"
    INSUFFICIENT = "insufficient"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AnalysisStatus(StrEnum):
    REQUESTED = "requested"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNING = "completed_with_warning"
    REJECTED_QUALITY = "rejected_quality"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ComparisonStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNING = "completed_with_warning"
    NON_COMPARABLE = "non_comparable"
    FAILED = "failed"


class ComparabilityStatus(StrEnum):
    COMPARABLE = "comparable"
    COMPARABLE_WITH_WARNING = "comparable_with_warning"
    PARTIALLY_COMPARABLE = "partially_comparable"
    NON_COMPARABLE = "non_comparable"
    UNKNOWN = "unknown"


class ReminderStatus(StrEnum):
    SCHEDULED = "scheduled"
    DUE = "due"
    OVERDUE = "overdue"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReminderOrigin(StrEnum):
    PHYSICIAN_REQUEST = "physician_request"
    TECHNICAL_QUALITY = "technical_quality"
    DEMONSTRATION_POLICY = "demonstration_policy"


@dataclass(frozen=True, slots=True)
class ECGWaveform:
    """Canonical waveform metadata; samples remain in the artifact store."""

    study_reference: str
    lead_names: tuple[str, ...]
    samples_per_lead: int
    sampling_rate_hz: float
    duration_seconds: float
    original_amplitude_unit: str
    normalized_amplitude_unit: str
    time_unit: str
    acquisition_at: datetime
    source_format: str
    source_device: str | None
    missing_leads: tuple[str, ...]
    parser_warnings: tuple[str, ...]
    preprocessing_version: str
    checksum: str
    conversion_method: str | None = None
    conversion_version: str | None = None
    calibration: str | None = None
    source_identifiers: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "study_reference", require_text(self.study_reference, "study_reference")
        )
        object.__setattr__(
            self, "acquisition_at", require_utc(self.acquisition_at, "acquisition_at")
        )
        if not self.lead_names or len(set(self.lead_names)) != len(self.lead_names):
            raise DomainInvariantError("waveform requires unique lead names")
        if self.samples_per_lead <= 0 or self.sampling_rate_hz <= 0 or self.duration_seconds <= 0:
            raise DomainInvariantError("waveform dimensions must be positive")
        if (
            self.original_amplitude_unit != self.normalized_amplitude_unit
            and not self.conversion_method
        ):
            raise DomainInvariantError("unit conversion provenance is required")


@dataclass(frozen=True, slots=True)
class ECGQualityResult:
    status: TechnicalQualityStatus
    reason_codes: tuple[str, ...]
    affected_leads: tuple[str, ...]
    parser_warnings: tuple[str, ...]
    preprocessing_warnings: tuple[str, ...]
    engine_version: str
    assessed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessed_at", require_utc(self.assessed_at, "assessed_at"))
        object.__setattr__(
            self, "engine_version", require_text(self.engine_version, "engine_version")
        )

    @property
    def suppress_score_emphasis(self) -> bool:
        return self.status.value in BLOCKING_QUALITY


@dataclass(slots=True)
class ECGIngestionJob(AggregateRoot):
    clinical_case_id: UUID
    source_type: ECGSourceType
    status: IngestionStatus
    requested_by: UUID
    requested_by_role: str
    requested_at: datetime
    correlation_id: UUID
    request_source: str
    idempotency_key: str
    study_reference: str
    acquisition_at: datetime
    content_type: str
    record_version: int = 1
    source_connector_id: str | None = None
    external_reference: str | None = None
    artifact_id: UUID | None = None
    resulting_study_id: UUID | None = None
    parser_name: str | None = None
    parser_version: str | None = None
    warnings: tuple[str, ...] = ()
    failure_category: str | None = None
    failure_detail_safe: str | None = None
    retry_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_of_job_id: UUID | None = None

    @classmethod
    def request(
        cls,
        *,
        clinical_case_id: UUID,
        source_type: ECGSourceType,
        requested_by: UUID,
        requested_by_role: str,
        requested_at: datetime,
        request_source: str,
        idempotency_key: str,
        study_reference: str,
        acquisition_at: datetime,
        content_type: str,
        context: EventContext,
        job_id: UUID | None = None,
        source_connector_id: str | None = None,
        external_reference: str | None = None,
    ) -> ECGIngestionJob:
        job = cls(
            id=job_id or uuid4(),
            clinical_case_id=clinical_case_id,
            source_type=source_type,
            status=IngestionStatus.REQUESTED,
            requested_by=requested_by,
            requested_by_role=require_text(requested_by_role, "requested_by_role"),
            requested_at=require_utc(requested_at, "requested_at"),
            correlation_id=context.correlation_id,
            request_source=require_text(request_source, "request_source"),
            idempotency_key=require_text(idempotency_key, "idempotency_key"),
            study_reference=require_text(study_reference, "study_reference"),
            acquisition_at=require_utc(acquisition_at, "acquisition_at"),
            content_type=require_text(content_type, "content_type"),
            source_connector_id=source_connector_id,
            external_reference=external_reference,
        )
        job._record_event(
            "ECGIngestionRequested.v1",
            1,
            {
                "case_id": str(clinical_case_id),
                "ingestion_job_id": str(job.id),
                "source_type": source_type.value,
            },
            context,
        )
        return job

    def start(self, occurred_at: datetime) -> None:
        if self.status is not IngestionStatus.REQUESTED:
            raise DomainInvariantError("ingestion job cannot start from its current state")
        self.status = IngestionStatus.RECEIVING
        self.started_at = require_utc(occurred_at, "started_at")
        self.record_version += 1

    def mark_retry(self, occurred_at: datetime, context: EventContext) -> None:
        if self.status not in {IngestionStatus.FAILED, IngestionStatus.REJECTED}:
            raise DomainInvariantError("only failed ingestion can be retried")
        if self.resulting_study_id is not None:
            raise DomainInvariantError("completed ingestion cannot be retried")
        self.status = IngestionStatus.REQUESTED
        self.retry_count += 1
        self.started_at = None
        self.completed_at = None
        self.failure_category = None
        self.failure_detail_safe = None
        self.record_version += 1
        self._record_event(
            "ECGIngestionRetried.v1",
            self.record_version,
            {
                "case_id": str(self.clinical_case_id),
                "ingestion_job_id": str(self.id),
                "retry_count": self.retry_count,
                "retried_at": require_utc(occurred_at, "retried_at").isoformat(),
                "resulting_version": self.record_version,
            },
            context,
        )

    def attach_source_artifact(self, artifact_id: UUID) -> None:
        if self.status is not IngestionStatus.RECEIVING:
            raise DomainInvariantError("source artifact can only be attached while receiving")
        self.artifact_id = artifact_id
        self.record_version += 1

    def complete(
        self,
        *,
        artifact_id: UUID,
        study_id: UUID,
        parser_name: str,
        parser_version: str,
        warnings: tuple[str, ...],
        completed_at: datetime,
        context: EventContext,
    ) -> None:
        if self.status not in {IngestionStatus.RECEIVING, IngestionStatus.ASSESSING_QUALITY}:
            raise DomainInvariantError("ingestion job cannot complete from its current state")
        self.status = IngestionStatus.COMPLETED
        self.artifact_id = artifact_id
        self.resulting_study_id = study_id
        self.parser_name = require_text(parser_name, "parser_name")
        self.parser_version = require_text(parser_version, "parser_version")
        self.warnings = warnings
        self.completed_at = require_utc(completed_at, "completed_at")
        self.record_version += 1
        self._record_event(
            "ECGIngestionCompleted.v1",
            self.record_version,
            {
                "case_id": str(self.clinical_case_id),
                "ingestion_job_id": str(self.id),
                "study_id": str(study_id),
                "artifact_id": str(artifact_id),
                "resulting_version": self.record_version,
            },
            context,
        )

    def fail(
        self, category: str, safe_detail: str, completed_at: datetime, context: EventContext
    ) -> None:
        self.status = IngestionStatus.FAILED
        self.failure_category = require_text(category, "failure_category")
        self.failure_detail_safe = require_text(safe_detail, "failure_detail_safe")
        self.completed_at = require_utc(completed_at, "completed_at")
        self.record_version += 1
        self._record_event(
            "ECGIngestionFailed.v1",
            self.record_version,
            {
                "case_id": str(self.clinical_case_id),
                "ingestion_job_id": str(self.id),
                "failure_category": self.failure_category,
                "resulting_version": self.record_version,
            },
            context,
        )


@dataclass(frozen=True, slots=True)
class LeadComparison:
    lead_name: str
    waveform_similarity: float
    normalized_difference: float
    amplitude_scale_change: float
    baseline_shift_indicator: float
    missing_data_percentage: float
    quality_difference: str
    sample_alignment_status: str = "aligned"


@dataclass(frozen=True, slots=True)
class ModelScoreEvolution:
    finding_code: str
    previous_score: float
    current_score: float
    absolute_delta: float
    previous_threshold_met: bool | None
    current_threshold_met: bool | None
    threshold_state_changed: bool | None
    previous_model_version: str
    current_model_version: str
    compatibility_status: str


@dataclass(frozen=True, slots=True)
class SignalFeatureDelta:
    """Technical signal-feature delta for serial ECG review, not a diagnosis."""

    feature_name: str
    display_label: str
    previous_value: float | None
    current_value: float | None
    absolute_delta: float | None
    unit: str | None
    status: str
    evidence_scope: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "feature_name", require_text(self.feature_name, "feature_name"))
        object.__setattr__(self, "display_label", require_text(self.display_label, "display_label"))
        object.__setattr__(self, "status", require_text(self.status, "status"))
        object.__setattr__(
            self, "evidence_scope", require_text(self.evidence_scope, "evidence_scope")
        )


@dataclass(frozen=True, slots=True)
class DynamicECGPhysicianReview:
    review_id: UUID
    comparison_id: UUID
    actor_id: UUID
    actor_role: str
    review_status: str
    interpretation: str
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: UUID
    record_version: int
    revision_number: int
    supersedes_review_id: UUID | None = None
    correction_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_status", require_text(self.review_status, "review_status"))
        object.__setattr__(
            self, "interpretation", require_text(self.interpretation, "interpretation")
        )
        object.__setattr__(self, "occurred_at", require_utc(self.occurred_at, "occurred_at"))
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))
        if self.revision_number < 1 or self.record_version < 1:
            raise DomainInvariantError("dynamic ECG review versions must be positive")
        if self.supersedes_review_id is not None and not self.correction_reason:
            raise DomainInvariantError("comparison review correction requires a reason")


@dataclass(slots=True)
class DynamicECGComparison(AggregateRoot):
    clinical_case_id: UUID
    baseline_study_id: UUID
    current_study_id: UUID
    comparison_policy_version: str
    preprocessing_version: str
    status: ComparisonStatus
    comparability_status: ComparabilityStatus
    comparability_reasons: tuple[str, ...]
    lead_comparisons: tuple[LeadComparison, ...]
    technical_change_indicators: tuple[str, ...]
    model_score_deltas: tuple[ModelScoreEvolution, ...]
    quality_context: str
    requested_by: UUID
    requested_at: datetime
    completed_at: datetime
    correlation_id: UUID
    record_version: int = 1
    requested_by_role: str = "unknown"
    started_at: datetime | None = None
    physician_review_status: str = "pending"
    model_score_compatibility: str = "not_available"
    signal_feature_deltas: tuple[SignalFeatureDelta, ...] = ()
    rhythm_change_indicators: tuple[str, ...] = ()
    st_t_change_indicators: tuple[str, ...] = ()
    review_recommendation: str = (
        "Technical serial ECG comparison only; physician interpretation is required."
    )

    def __post_init__(self) -> None:
        if self.baseline_study_id == self.current_study_id:
            raise DomainInvariantError("dynamic comparison requires two distinct studies")
        if (
            self.comparability_status is ComparabilityStatus.NON_COMPARABLE
            and self.lead_comparisons
        ):
            raise DomainInvariantError("non-comparable studies cannot contain lead comparisons")
        if not self.review_recommendation.strip():
            raise DomainInvariantError("dynamic comparison requires a review recommendation")


@dataclass(slots=True)
class ECGRepeatReminder(AggregateRoot):
    clinical_case_id: UUID
    source_study_id: UUID
    requested_by: UUID
    reason: str
    due_at: datetime
    status: ReminderStatus
    created_at: datetime
    correlation_id: UUID
    record_version: int = 1
    requested_by_role: str = "unknown"
    origin: ReminderOrigin = ReminderOrigin.PHYSICIAN_REQUEST
    updated_at: datetime | None = None
    acknowledged_by: UUID | None = None
    acknowledged_at: datetime | None = None
    completed_study_id: UUID | None = None
    completed_at: datetime | None = None
    cancelled_by: UUID | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None

    def effective_status(self, now: datetime) -> ReminderStatus:
        now = require_utc(now, "now")
        active_statuses = {
            ReminderStatus.SCHEDULED,
            ReminderStatus.DUE,
            ReminderStatus.OVERDUE,
        }
        if self.status not in active_statuses:
            return self.status
        if now > self.due_at:
            return ReminderStatus.OVERDUE
        if now == self.due_at:
            return ReminderStatus.DUE
        return ReminderStatus.SCHEDULED

    def acknowledge(self, actor_id: UUID, occurred_at: datetime, context: EventContext) -> None:
        if self.status not in {
            ReminderStatus.SCHEDULED,
            ReminderStatus.DUE,
            ReminderStatus.OVERDUE,
        }:
            raise DomainInvariantError("reminder cannot be acknowledged from its current state")
        self.status = ReminderStatus.ACKNOWLEDGED
        self.acknowledged_by = actor_id
        self.acknowledged_at = require_utc(occurred_at, "acknowledged_at")
        self.updated_at = self.acknowledged_at
        self.record_version += 1
        self._record_event(
            "RepeatECGReminderAcknowledged.v1",
            self.record_version,
            {
                "case_id": str(self.clinical_case_id),
                "reminder_id": str(self.id),
                "resulting_version": self.record_version,
            },
            context,
        )

    def complete(self, study_id: UUID, occurred_at: datetime, context: EventContext) -> None:
        if self.status is ReminderStatus.COMPLETED:
            if self.completed_study_id == study_id:
                return
            raise DomainInvariantError("completed reminder cannot be linked to another study")
        if self.status is ReminderStatus.CANCELLED:
            raise DomainInvariantError("cancelled reminder cannot be completed")
        self.status = ReminderStatus.COMPLETED
        self.completed_study_id = study_id
        self.completed_at = require_utc(occurred_at, "completed_at")
        self.updated_at = self.completed_at
        self.record_version += 1
        self._record_event(
            "RepeatECGReminderCompleted.v1",
            self.record_version,
            {
                "case_id": str(self.clinical_case_id),
                "reminder_id": str(self.id),
                "study_id": str(study_id),
                "completed_at": self.completed_at.isoformat(),
                "resulting_version": self.record_version,
            },
            context,
        )

    def cancel(
        self,
        actor_id: UUID,
        reason: str,
        occurred_at: datetime,
        context: EventContext,
    ) -> None:
        if self.status in {ReminderStatus.COMPLETED, ReminderStatus.CANCELLED}:
            raise DomainInvariantError("reminder cannot be cancelled from its current state")
        self.status = ReminderStatus.CANCELLED
        self.cancelled_by = actor_id
        self.cancelled_at = require_utc(occurred_at, "cancelled_at")
        self.cancellation_reason = require_text(reason, "cancellation_reason")
        self.updated_at = self.cancelled_at
        self.record_version += 1
        self._record_event(
            "RepeatECGReminderCancelled.v1",
            self.record_version,
            {
                "case_id": str(self.clinical_case_id),
                "reminder_id": str(self.id),
                "reason": self.cancellation_reason,
                "resulting_version": self.record_version,
            },
            context,
        )
