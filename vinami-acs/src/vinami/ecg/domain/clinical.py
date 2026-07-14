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
    LIMITED = "limited"
    NON_COMPARABLE = "non_comparable"


class ReminderStatus(StrEnum):
    SCHEDULED = "scheduled"
    DUE = "due"
    OVERDUE = "overdue"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


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
    requested_at: datetime
    correlation_id: UUID
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

    @classmethod
    def request(
        cls,
        *,
        clinical_case_id: UUID,
        source_type: ECGSourceType,
        requested_by: UUID,
        requested_at: datetime,
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
            requested_at=require_utc(requested_at, "requested_at"),
            correlation_id=context.correlation_id,
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
        if self.status not in {IngestionStatus.REQUESTED, IngestionStatus.FAILED}:
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
    model_score_deltas: tuple[tuple[str, float, float, float], ...]
    quality_context: str
    requested_by: UUID
    requested_at: datetime
    completed_at: datetime
    correlation_id: UUID
    record_version: int = 1

    def __post_init__(self) -> None:
        if self.baseline_study_id == self.current_study_id:
            raise DomainInvariantError("dynamic comparison requires two distinct studies")
        if (
            self.comparability_status is ComparabilityStatus.NON_COMPARABLE
            and self.lead_comparisons
        ):
            raise DomainInvariantError("non-comparable studies cannot contain lead comparisons")


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
    acknowledged_by: UUID | None = None
    acknowledged_at: datetime | None = None
    completed_study_id: UUID | None = None

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
        self.record_version += 1
        self._record_event(
            "RepeatECGReminderCompleted.v1",
            self.record_version,
            {
                "case_id": str(self.clinical_case_id),
                "reminder_id": str(self.id),
                "study_id": str(study_id),
                "completed_at": require_utc(occurred_at, "completed_at").isoformat(),
                "resulting_version": self.record_version,
            },
            context,
        )
