"""Persistence port for ECG evidence and normalized AI results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from vinami.ecg.domain.clinical import (
    DynamicECGComparison,
    DynamicECGPhysicianReview,
    ECGIngestionJob,
    ECGQualityResult,
    ECGRepeatReminder,
    ECGSourceType,
    ECGWaveform,
)
from vinami.ecg.domain.model import ECGStudy
from vinami.ecg.ports.artifacts import ArtifactMetadata


@dataclass(frozen=True, slots=True)
class ECGFindingSnapshot:
    """One normalized, ranked model output without diagnostic semantics."""

    finding_code: str
    display_label: str
    model_score: float
    threshold: float | None
    threshold_met: bool | None
    rank: int
    finding_status: str
    explanation_reference: str | None


class ECGStudyRepository(Protocol):
    """Persist and retrieve ECG study evidence without importing a model provider."""

    def add(self, study: ECGStudy) -> None:
        """Stage a newly uploaded ECG study."""

    def get(self, study_id: UUID) -> ECGStudy | None:
        """Return a study by UUID when it exists."""

    def save(self, study: ECGStudy) -> None:
        """Persist quality or normalized AI-result updates for a study."""


@dataclass(frozen=True, slots=True)
class ECGStudySnapshot:
    study_id: UUID
    clinical_case_id: UUID
    encounter_id: UUID
    study_reference: str
    source_type: ECGSourceType
    source_system: str
    source_connector_id: str | None
    acquisition_device: str | None
    acquisition_at: datetime
    ingestion_at: datetime
    study_status: str
    lead_configuration: str
    sampling_rate_hz: float | None
    duration_seconds: float | None
    amplitude_unit: str | None
    raw_artifact_id: UUID
    normalized_waveform_artifact_id: UUID | None
    preview_artifact_id: UUID | None
    source_format: str
    source_content_type: str
    artifact_checksum: str
    artifact_size: int
    parser_version: str
    preprocessing_version: str | None
    quality_status: str
    created_by_actor_id: UUID
    created_by_actor_role: str
    correlation_id: UUID
    aggregate_version: int
    created_at: datetime
    updated_at: datetime
    waveform_available: bool


@dataclass(frozen=True, slots=True)
class ECGAnalysisSnapshot:
    analysis_id: UUID
    ecg_study_id: UUID
    provider_name: str
    provider_version: str
    model_name: str
    model_version: str
    model_checksum: str | None
    preprocessing_version: str
    label_mapping_version: str
    threshold_version: str | None
    input_artifact_id: UUID
    input_artifact_checksum: str
    status: str
    quality_status: str
    requested_by: UUID
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    inference_duration_ms: int | None
    findings: tuple[ECGFindingSnapshot, ...]
    warnings: tuple[str, ...]
    explanation_status: str
    explanation_artifact_id: UUID | None
    failure_category: str | None
    failure_detail_safe: str | None
    correlation_id: UUID
    record_version: int
    synthetic: bool


@dataclass(frozen=True, slots=True)
class PhysicianInterpretationSnapshot:
    interpretation_id: UUID
    ecg_study_id: UUID
    analysis_id: UUID | None
    actor_id: UUID
    actor_role: str
    interpretation_status: str
    structured_interpretation: str
    agreement_status: str
    disagreement_reason: str | None
    quality_disposition: str
    repeat_ecg_requested: bool
    note: str | None
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: UUID
    record_version: int
    revision_number: int
    supersedes_interpretation_id: UUID | None
    correction_reason: str | None


@dataclass(frozen=True, slots=True)
class ECGWorkspaceSnapshot:
    """Typed case-level ECG read model consumed by API delivery adapters."""

    clinical_case_id: UUID
    studies: tuple[ECGStudySnapshot, ...]
    current_study: ECGStudySnapshot | None
    quality: ECGQualityResult | None
    analyses: tuple[ECGAnalysisSnapshot, ...]
    interpretations: tuple[PhysicianInterpretationSnapshot, ...]
    ingestion_jobs: tuple[ECGIngestionJob, ...]
    comparisons: tuple[DynamicECGComparison, ...]
    comparison_reviews: tuple[DynamicECGPhysicianReview, ...]
    reminders: tuple[ECGRepeatReminder, ...]
    safety_notice: str


class ECGClinicalRepository(Protocol):
    def add_artifact(self, value: ArtifactMetadata) -> None: ...
    def get_artifact(self, artifact_id: UUID) -> ArtifactMetadata | None: ...
    def add_ingestion_job(self, value: ECGIngestionJob) -> None: ...
    def get_ingestion_job(self, job_id: UUID) -> ECGIngestionJob | None: ...
    def save_ingestion_job(self, value: ECGIngestionJob) -> None: ...
    def list_ingestion_jobs(self, case_id: UUID) -> tuple[ECGIngestionJob, ...]: ...
    def add_study(
        self, value: ECGStudySnapshot, waveform: ECGWaveform | None, quality: ECGQualityResult
    ) -> None: ...
    def get_study(self, study_id: UUID) -> ECGStudySnapshot | None: ...
    def list_studies(self, case_id: UUID) -> tuple[ECGStudySnapshot, ...]: ...
    def get_waveform(self, study_id: UUID) -> ECGWaveform | None: ...
    def get_quality(self, study_id: UUID) -> ECGQualityResult | None: ...
    def add_analysis(self, value: ECGAnalysisSnapshot) -> None: ...
    def get_analysis(self, analysis_id: UUID) -> ECGAnalysisSnapshot | None: ...
    def list_analyses(self, study_id: UUID) -> tuple[ECGAnalysisSnapshot, ...]: ...
    def add_interpretation(self, value: PhysicianInterpretationSnapshot) -> None: ...
    def get_interpretation(
        self, interpretation_id: UUID
    ) -> PhysicianInterpretationSnapshot | None: ...
    def list_interpretations(
        self, study_id: UUID
    ) -> tuple[PhysicianInterpretationSnapshot, ...]: ...
    def add_comparison(self, value: DynamicECGComparison) -> None: ...
    def get_comparison(self, comparison_id: UUID) -> DynamicECGComparison | None: ...
    def list_comparisons(self, case_id: UUID) -> tuple[DynamicECGComparison, ...]: ...
    def add_comparison_review(self, value: DynamicECGPhysicianReview) -> None: ...
    def get_comparison_review(self, review_id: UUID) -> DynamicECGPhysicianReview | None: ...
    def list_comparison_reviews(
        self, comparison_id: UUID
    ) -> tuple[DynamicECGPhysicianReview, ...]: ...
    def add_reminder(self, value: ECGRepeatReminder) -> None: ...
    def get_reminder(self, reminder_id: UUID) -> ECGRepeatReminder | None: ...
    def save_reminder(self, value: ECGRepeatReminder, expected_version: int) -> None: ...
    def list_reminders(self, case_id: UUID) -> tuple[ECGRepeatReminder, ...]: ...
