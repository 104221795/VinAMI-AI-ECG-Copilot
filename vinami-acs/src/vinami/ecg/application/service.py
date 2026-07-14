"""R3 ECG application commands and queries coordinated through ports and one UoW."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from time import perf_counter
from typing import Protocol
from uuid import UUID, uuid4

from vinami.clinical_case.ports.repository import ClinicalCaseRepository
from vinami.ecg.domain.clinical import (
    BLOCKING_QUALITY,
    ComparabilityStatus,
    ComparisonStatus,
    DynamicECGComparison,
    ECGIngestionJob,
    ECGQualityResult,
    ECGRepeatReminder,
    ECGSourceType,
    LeadComparison,
    ReminderStatus,
    TechnicalQualityStatus,
)
from vinami.ecg.ports.artifacts import ArtifactMetadata, ECGArtifactStore
from vinami.ecg.ports.ingestion import (
    DICOMSourceConnector,
    ECGSourceAdapter,
    ParsedWaveform,
    SourceInfo,
)
from vinami.ecg.ports.preprocessing import ECGPreprocessor, ECGQualityEngine
from vinami.ecg.ports.provider import (
    AIProviderHealth,
    ECGAIProvider,
    ECGExplanationRequest,
    ECGPredictionRequest,
    ModelInfo,
)
from vinami.ecg.ports.repository import (
    ECGAnalysisSnapshot,
    ECGClinicalRepository,
    ECGFindingSnapshot,
    ECGStudySnapshot,
    ECGWorkspaceSnapshot,
    PhysicianInterpretationSnapshot,
)
from vinami.patient.application.lifecycle import ActorRepository
from vinami.patient.ports.repository import EncounterRepository
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import ResourceConflictError, ResourceNotFoundError
from vinami.shared.domain import (
    AggregateRoot,
    OptimisticConcurrencyError,
    require_text,
    require_utc,
    utc_now,
)
from vinami.shared.events.contracts import EventContext, EventEnvelope
from vinami.shared.idempotency import IdempotencyRepository, IdempotencyResult, command_fingerprint

SAFE_LABELS = {
    "NORM": "NORM",
    "MI": "MI-related ECG pattern",
    "STTC": "ST/T change",
    "CD": "conduction disturbance",
    "HYP": "hypertrophy pattern",
}


class ECGUnitOfWork(Protocol):
    cases: ClinicalCaseRepository
    encounters: EncounterRepository
    actors: ActorRepository
    idempotency: IdempotencyRepository
    ecg_clinical: ECGClinicalRepository

    def __enter__(self) -> ECGUnitOfWork: ...
    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None: ...
    def collect_events(self, aggregates: Iterable[AggregateRoot]) -> None: ...
    def stage_event(self, event: EventEnvelope) -> None: ...
    def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> ECGUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class IngestECG:
    actor: ActorContext
    idempotency_key: str
    clinical_case_id: UUID
    source_type: ECGSourceType
    study_reference: str
    acquisition_at: datetime
    content: bytes | None
    content_type: str
    original_filename: str | None = None
    source_connector_id: str | None = None
    external_reference: str | None = None
    expected_case_version: int | None = None


@dataclass(frozen=True, slots=True)
class RequestAnalysis:
    actor: ActorContext
    idempotency_key: str
    study_id: UUID
    provider_name: str


@dataclass(frozen=True, slots=True)
class RecordInterpretation:
    actor: ActorContext
    idempotency_key: str
    study_id: UUID
    analysis_id: UUID | None
    interpretation_status: str
    structured_interpretation: str
    agreement_status: str
    disagreement_reason: str | None
    quality_disposition: str
    repeat_ecg_requested: bool
    note: str | None
    occurred_at: datetime
    expected_version: int
    supersedes_interpretation_id: UUID | None = None
    correction_reason: str | None = None


@dataclass(frozen=True, slots=True)
class RequestComparison:
    actor: ActorContext
    idempotency_key: str
    clinical_case_id: UUID
    baseline_study_id: UUID
    current_study_id: UUID


@dataclass(frozen=True, slots=True)
class ScheduleReminder:
    actor: ActorContext
    idempotency_key: str
    clinical_case_id: UUID
    source_study_id: UUID
    reason: str
    due_at: datetime


class ECGApplicationService:
    """Coordinate ECG product behavior without importing parsers, ORM, or model frameworks."""

    def __init__(
        self,
        unit_of_work: UnitOfWorkFactory,
        artifact_store: ECGArtifactStore,
        source_adapters: dict[str, ECGSourceAdapter],
        preprocessor: ECGPreprocessor,
        quality_engine: ECGQualityEngine,
        providers: dict[str, ECGAIProvider],
        dicom_connector: DICOMSourceConnector,
    ) -> None:
        self._uow = unit_of_work
        self._artifacts = artifact_store
        self._sources = source_adapters
        self._preprocessor = preprocessor
        self._quality = quality_engine
        self._providers = providers
        self._dicom_connector = dicom_connector

    def ingest(self, command: IngestECG) -> tuple[ECGIngestionJob, ECGStudySnapshot | None]:
        payload = {
            "case_id": str(command.clinical_case_id),
            "source_type": command.source_type.value,
            "study_reference": command.study_reference,
            "acquisition_at": command.acquisition_at.isoformat(),
            "content_type": command.content_type,
            "external_reference": command.external_reference,
        }
        fingerprint = command_fingerprint(payload)
        with self._uow() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow, command.actor, "IngestECG", command.idempotency_key, fingerprint
            )
            if previous:
                job = uow.ecg_clinical.get_ingestion_job(
                    UUID(str(previous.response_payload["job_id"]))
                )
                if job is None:
                    raise ResourceConflictError("stored ECG ingestion result is unavailable")
                return job, uow.ecg_clinical.get_study(
                    job.resulting_study_id
                ) if job.resulting_study_id else None
            case = uow.cases.get(command.clinical_case_id)
            if case is None:
                raise ResourceNotFoundError("clinical case not found")
            if (
                command.expected_case_version is not None
                and case.version != command.expected_case_version
            ):
                raise OptimisticConcurrencyError("clinical case has a newer version")
            encounter = uow.encounters.get(case.encounter_id)
            if encounter is None:
                raise ResourceNotFoundError("encounter not found")
            context = _context(command.actor)
            now = utc_now()
            job = ECGIngestionJob.request(
                clinical_case_id=case.id,
                source_type=command.source_type,
                requested_by=command.actor.actor_id,
                requested_at=now,
                context=context,
                source_connector_id=command.source_connector_id,
                external_reference=command.external_reference,
            )
            uow.ecg_clinical.add_ingestion_job(job)
            try:
                content = self._resolve_content(command)
                adapter = self._source(command.source_type)
                adapter.validate_source(content, command.content_type)
                raw = self._artifacts.write(
                    content,
                    artifact_kind="raw_source",
                    content_type=command.content_type,
                    original_filename=command.original_filename,
                )
                uow.ecg_clinical.add_artifact(raw)
                parsed = adapter.parse(
                    content,
                    study_reference=require_text(command.study_reference, "study_reference"),
                    acquisition_at=require_utc(command.acquisition_at, "acquisition_at"),
                )
                normalized_artifact = None
                waveform = None
                if isinstance(parsed, ParsedWaveform):
                    normalized = self._preprocessor.normalize(parsed)
                    waveform = normalized.waveform
                    normalized_artifact = self._artifacts.write(
                        normalized.normalized_content,
                        artifact_kind="normalized_waveform",
                        content_type="application/vnd.vinami.ecg+json",
                    )
                    uow.ecg_clinical.add_artifact(normalized_artifact)
                    quality = self._quality.assess(parsed, normalized)
                else:
                    quality = ECGQualityResult(
                        TechnicalQualityStatus.UNSUPPORTED,
                        ("structured_waveform_unavailable",),
                        (),
                        parsed.parser_warnings,
                        (),
                        "technical-quality-1.0.0",
                        now,
                    )
                preview_value = adapter.create_preview(content, parsed)
                preview = None
                if preview_value:
                    preview = self._artifacts.write(
                        preview_value[0], artifact_kind="preview", content_type=preview_value[1]
                    )
                    uow.ecg_clinical.add_artifact(preview)
                study = ECGStudySnapshot(
                    study_id=uuid4(),
                    clinical_case_id=case.id,
                    encounter_id=encounter.id,
                    study_reference=command.study_reference,
                    source_type=command.source_type,
                    source_system=command.source_connector_id or "local-upload",
                    source_connector_id=command.source_connector_id,
                    acquisition_device=parsed.source_device
                    if isinstance(parsed, ParsedWaveform)
                    else None,
                    acquisition_at=command.acquisition_at,
                    ingestion_at=now,
                    study_status="ready_for_review",
                    lead_configuration=f"{len(waveform.lead_names)}-lead"
                    if waveform
                    else "document-only",
                    sampling_rate_hz=waveform.sampling_rate_hz if waveform else None,
                    duration_seconds=waveform.duration_seconds if waveform else None,
                    amplitude_unit=waveform.normalized_amplitude_unit if waveform else None,
                    raw_artifact_id=raw.artifact_id,
                    normalized_waveform_artifact_id=normalized_artifact.artifact_id
                    if normalized_artifact
                    else None,
                    preview_artifact_id=preview.artifact_id if preview else None,
                    source_format=parsed.source_format,
                    source_content_type=raw.content_type,
                    artifact_checksum=raw.checksum_sha256,
                    artifact_size=raw.size_bytes,
                    parser_version=parsed.parser_version,
                    preprocessing_version=waveform.preprocessing_version if waveform else None,
                    quality_status=quality.status.value,
                    created_by_actor_id=command.actor.actor_id,
                    created_by_actor_role=command.actor.actor_role,
                    correlation_id=command.actor.correlation_id,
                    aggregate_version=1,
                    created_at=now,
                    updated_at=now,
                    waveform_available=waveform is not None,
                )
                uow.ecg_clinical.add_study(study, waveform, quality)
                job.complete(
                    artifact_id=raw.artifact_id,
                    study_id=study.study_id,
                    parser_name=parsed.parser_name,
                    parser_version=parsed.parser_version,
                    warnings=parsed.parser_warnings,
                    completed_at=now,
                    context=context,
                )
                uow.ecg_clinical.save_ingestion_job(job)
                uow.stage_event(
                    _event(
                        "ECGStudyCreated.v1",
                        study.study_id,
                        1,
                        {
                            "case_id": str(case.id),
                            "study_id": str(study.study_id),
                            "source_type": study.source_type.value,
                        },
                        command.actor,
                    )
                )
                uow.stage_event(
                    _event(
                        "ECGQualityAssessed.v1",
                        study.study_id,
                        1,
                        {
                            "case_id": str(case.id),
                            "study_id": str(study.study_id),
                            "quality_status": quality.status.value,
                        },
                        command.actor,
                    )
                )
                response: dict[str, object] = {
                    "job_id": str(job.id),
                    "study_id": str(study.study_id),
                }
                _store_idempotency(
                    uow,
                    command.actor,
                    "IngestECG",
                    command.idempotency_key,
                    fingerprint,
                    job.id,
                    response,
                    now,
                )
                uow.collect_events([job])
                uow.commit()
                return job, study
            except Exception as error:
                job.fail(type(error).__name__, _safe_failure(error), utc_now(), context)
                uow.ecg_clinical.save_ingestion_job(job)
                uow.collect_events([job])
                uow.commit()
                raise

    def request_analysis(self, command: RequestAnalysis) -> ECGAnalysisSnapshot:
        fingerprint = command_fingerprint(
            {"study_id": str(command.study_id), "provider": command.provider_name}
        )
        with self._uow() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow, command.actor, "RequestECGAnalysis", command.idempotency_key, fingerprint
            )
            if previous:
                value = uow.ecg_clinical.get_analysis(
                    UUID(str(previous.response_payload["analysis_id"]))
                )
                if value is None:
                    raise ResourceConflictError("stored analysis result is unavailable")
                return value
            study = uow.ecg_clinical.get_study(command.study_id)
            if study is None:
                raise ResourceNotFoundError("ECG study not found")
            if not study.waveform_available or study.normalized_waveform_artifact_id is None:
                raise ResourceConflictError(
                    "structured waveform is unavailable for automated analysis"
                )
            provider = self._providers.get(command.provider_name)
            if provider is None:
                raise ResourceConflictError("ECG AI provider is not configured")
            model = provider.get_model_info()
            requested_at = utc_now()
            analysis_id = uuid4()
            uow.stage_event(
                _event(
                    "ECGAnalysisRequested.v1",
                    analysis_id,
                    1,
                    {
                        "case_id": str(study.clinical_case_id),
                        "study_id": str(study.study_id),
                        "analysis_id": str(analysis_id),
                        "provider": model.provider_name,
                    },
                    command.actor,
                    "ECGAIAnalysis",
                )
            )
            started = perf_counter()
            status = "completed"
            failure_category = None
            failure_detail = None
            explanation_artifact = None
            try:
                result = provider.predict(
                    ECGPredictionRequest(
                        study.study_id,
                        f"artifact://{study.normalized_waveform_artifact_id}",
                        input_quality=study.quality_status,
                        artifact_checksum=study.artifact_checksum,
                    )
                )
                if result.failure_reason:
                    status = "rejected_quality"
                findings = _findings(result.label_scores, result.thresholds, model)
                if study.quality_status in BLOCKING_QUALITY:
                    findings = ()
                if findings and status == "completed":
                    explanation = provider.explain(
                        ECGExplanationRequest(
                            study.study_id,
                            f"analysis://{analysis_id}",
                            findings[0].finding_code,
                        )
                    )
                    if explanation.content and explanation.content_type:
                        explanation_artifact = self._artifacts.write(
                            explanation.content,
                            artifact_kind="explanation",
                            content_type=explanation.content_type,
                        )
                        uow.ecg_clinical.add_artifact(explanation_artifact)
                warnings = result.warnings
                completed_at = result.completed_at
                started_at = result.started_at
                synthetic = result.synthetic
            except TimeoutError as error:
                status, failure_category, failure_detail = (
                    "timed_out",
                    "provider_timeout",
                    _safe_failure(error),
                )
                findings, warnings, completed_at, started_at, synthetic = (
                    (),
                    (),
                    utc_now(),
                    requested_at,
                    model.synthetic,
                )
            except Exception as error:
                status, failure_category, failure_detail = (
                    "failed",
                    "provider_failure",
                    _safe_failure(error),
                )
                findings, warnings, completed_at, started_at, synthetic = (
                    (),
                    (),
                    utc_now(),
                    requested_at,
                    model.synthetic,
                )
            duration_ms = max(0, round((perf_counter() - started) * 1000))
            value = ECGAnalysisSnapshot(
                analysis_id,
                study.study_id,
                model.provider_name,
                model.version,
                model.name,
                model.version,
                model.checkpoint_checksum,
                study.preprocessing_version or "none",
                "safe-labels-r3-v1",
                model.threshold_source,
                study.normalized_waveform_artifact_id,
                study.artifact_checksum,
                status,
                study.quality_status,
                command.actor.actor_id,
                requested_at,
                started_at,
                completed_at,
                duration_ms,
                findings,
                warnings,
                "available" if explanation_artifact else "unavailable",
                explanation_artifact.artifact_id if explanation_artifact else None,
                failure_category,
                failure_detail,
                command.actor.correlation_id,
                1,
                synthetic,
            )
            uow.ecg_clinical.add_analysis(value)
            event_type = (
                "ECGAnalysisCompleted.v1"
                if status in {"completed", "completed_with_warning", "rejected_quality"}
                else "ECGAnalysisFailed.v1"
            )
            uow.stage_event(
                _event(
                    event_type,
                    analysis_id,
                    1,
                    {
                        "case_id": str(study.clinical_case_id),
                        "study_id": str(study.study_id),
                        "analysis_id": str(analysis_id),
                        "status": status,
                        "model_name": model.name,
                        "model_version": model.version,
                        "synthetic": synthetic,
                    },
                    command.actor,
                    "ECGAIAnalysis",
                )
            )
            _store_idempotency(
                uow,
                command.actor,
                "RequestECGAnalysis",
                command.idempotency_key,
                fingerprint,
                analysis_id,
                {"analysis_id": str(analysis_id)},
                requested_at,
            )
            uow.commit()
            return value

    def record_interpretation(
        self, command: RecordInterpretation
    ) -> PhysicianInterpretationSnapshot:
        command.actor.require_physician()
        fingerprint = command_fingerprint(
            {
                "study_id": str(command.study_id),
                "analysis_id": str(command.analysis_id),
                "status": command.interpretation_status,
                "text": command.structured_interpretation,
                "agreement": command.agreement_status,
                "repeat": command.repeat_ecg_requested,
                "supersedes": str(command.supersedes_interpretation_id),
                "reason": command.correction_reason,
            }
        )
        with self._uow() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow,
                command.actor,
                "RecordPhysicianECGInterpretation",
                command.idempotency_key,
                fingerprint,
            )
            if previous:
                value = uow.ecg_clinical.get_interpretation(
                    UUID(str(previous.response_payload["interpretation_id"]))
                )
                if value is None:
                    raise ResourceConflictError("stored interpretation is unavailable")
                return value
            study = uow.ecg_clinical.get_study(command.study_id)
            if study is None:
                raise ResourceNotFoundError("ECG study not found")
            history = uow.ecg_clinical.list_interpretations(command.study_id)
            latest = history[0] if history else None
            current_version = latest.record_version if latest else 0
            if current_version != command.expected_version:
                raise OptimisticConcurrencyError(
                    "physician ECG interpretation has a newer revision"
                )
            if command.supersedes_interpretation_id:
                if (
                    latest is None
                    or latest.interpretation_id != command.supersedes_interpretation_id
                ):
                    raise OptimisticConcurrencyError(
                        "interpretation correction does not target the latest revision"
                    )
                require_text(command.correction_reason or "", "correction_reason")
            now = utc_now()
            value = PhysicianInterpretationSnapshot(
                uuid4(),
                command.study_id,
                command.analysis_id,
                command.actor.actor_id,
                command.actor.actor_role,
                require_text(command.interpretation_status, "interpretation_status"),
                require_text(command.structured_interpretation, "structured_interpretation"),
                require_text(command.agreement_status, "agreement_status"),
                command.disagreement_reason,
                require_text(command.quality_disposition, "quality_disposition"),
                command.repeat_ecg_requested,
                command.note,
                require_utc(command.occurred_at, "occurred_at"),
                now,
                command.actor.correlation_id,
                current_version + 1,
                len(history) + 1,
                command.supersedes_interpretation_id,
                command.correction_reason,
            )
            uow.ecg_clinical.add_interpretation(value)
            event_type = (
                "PhysicianECGInterpretationCorrected.v1"
                if latest
                else "PhysicianECGInterpretationRecorded.v1"
            )
            uow.stage_event(
                _event(
                    event_type,
                    value.interpretation_id,
                    value.record_version,
                    {
                        "case_id": str(study.clinical_case_id),
                        "study_id": str(study.study_id),
                        "interpretation_id": str(value.interpretation_id),
                        "agreement_status": value.agreement_status,
                        "repeat_ecg_requested": value.repeat_ecg_requested,
                        "reason": value.correction_reason,
                        "resulting_version": value.record_version,
                    },
                    command.actor,
                    "PhysicianECGInterpretation",
                )
            )
            _store_idempotency(
                uow,
                command.actor,
                "RecordPhysicianECGInterpretation",
                command.idempotency_key,
                fingerprint,
                value.interpretation_id,
                {"interpretation_id": str(value.interpretation_id)},
                now,
            )
            uow.commit()
            return value

    def compare(self, command: RequestComparison) -> DynamicECGComparison:
        fingerprint = command_fingerprint(
            {
                "case_id": str(command.clinical_case_id),
                "baseline": str(command.baseline_study_id),
                "current": str(command.current_study_id),
            }
        )
        with self._uow() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow,
                command.actor,
                "RequestDynamicECGComparison",
                command.idempotency_key,
                fingerprint,
            )
            if previous:
                value = uow.ecg_clinical.get_comparison(
                    UUID(str(previous.response_payload["comparison_id"]))
                )
                if value is None:
                    raise ResourceConflictError("stored comparison is unavailable")
                return value
            baseline = uow.ecg_clinical.get_study(command.baseline_study_id)
            current = uow.ecg_clinical.get_study(command.current_study_id)
            if (
                baseline is None
                or current is None
                or baseline.clinical_case_id != command.clinical_case_id
                or current.clinical_case_id != command.clinical_case_id
            ):
                raise ResourceNotFoundError("serial ECG study not found in this case")
            reasons = _comparability_reasons(baseline, current)
            lead_values: tuple[LeadComparison, ...] = ()
            indicators: tuple[str, ...]
            if reasons:
                comparability = ComparabilityStatus.NON_COMPARABLE
                status = ComparisonStatus.NON_COMPARABLE
                indicators = ("studies not comparable", "physician review required")
            else:
                baseline_samples = self._samples(baseline)
                current_samples = self._samples(current)
                lead_values = _compare_leads(baseline_samples, current_samples)
                changed = sum(1 for item in lead_values if item.normalized_difference >= 0.15)
                indicators = (
                    ("multiple leads changed", "physician review required")
                    if changed >= 2
                    else ("technical change detected", "physician review required")
                    if changed
                    else ("no material technical change detected", "physician review required")
                )
                comparability = ComparabilityStatus.COMPARABLE
                status = ComparisonStatus.COMPLETED
            now = utc_now()
            score_deltas = _score_deltas(
                uow.ecg_clinical.list_analyses(baseline.study_id),
                uow.ecg_clinical.list_analyses(current.study_id),
            )
            value = DynamicECGComparison(
                uuid4(),
                command.clinical_case_id,
                baseline.study_id,
                current.study_id,
                "technical-comparison-1.0.0",
                current.preprocessing_version or "none",
                status,
                comparability,
                tuple(reasons),
                lead_values,
                tuple(indicators),
                score_deltas,
                f"baseline={baseline.quality_status}; current={current.quality_status}",
                command.actor.actor_id,
                now,
                now,
                command.actor.correlation_id,
            )
            uow.ecg_clinical.add_comparison(value)
            event_type = (
                "DynamicECGComparisonCompleted.v1"
                if status is not ComparisonStatus.NON_COMPARABLE
                else "DynamicECGComparisonFailed.v1"
            )
            uow.stage_event(
                _event(
                    event_type,
                    value.id,
                    1,
                    {
                        "case_id": str(command.clinical_case_id),
                        "comparison_id": str(value.id),
                        "baseline_study_id": str(baseline.study_id),
                        "current_study_id": str(current.study_id),
                        "comparability_status": comparability.value,
                    },
                    command.actor,
                    "DynamicECGComparison",
                )
            )
            _store_idempotency(
                uow,
                command.actor,
                "RequestDynamicECGComparison",
                command.idempotency_key,
                fingerprint,
                value.id,
                {"comparison_id": str(value.id)},
                now,
            )
            uow.commit()
            return value

    def schedule_reminder(self, command: ScheduleReminder) -> ECGRepeatReminder:
        require_utc(command.due_at, "due_at")
        fingerprint = command_fingerprint(
            {
                "case_id": str(command.clinical_case_id),
                "study_id": str(command.source_study_id),
                "reason": command.reason,
                "due_at": command.due_at.isoformat(),
            }
        )
        with self._uow() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(
                uow,
                command.actor,
                "ScheduleRepeatECGReminder",
                command.idempotency_key,
                fingerprint,
            )
            if previous:
                value = uow.ecg_clinical.get_reminder(
                    UUID(str(previous.response_payload["reminder_id"]))
                )
                if value is None:
                    raise ResourceConflictError("stored reminder is unavailable")
                return value
            study = uow.ecg_clinical.get_study(command.source_study_id)
            if study is None or study.clinical_case_id != command.clinical_case_id:
                raise ResourceNotFoundError("source ECG study not found")
            now = utc_now()
            value = ECGRepeatReminder(
                uuid4(),
                command.clinical_case_id,
                command.source_study_id,
                command.actor.actor_id,
                require_text(command.reason, "reason"),
                command.due_at,
                ReminderStatus.SCHEDULED,
                now,
                command.actor.correlation_id,
            )
            uow.ecg_clinical.add_reminder(value)
            uow.stage_event(
                _event(
                    "RepeatECGReminderScheduled.v1",
                    value.id,
                    1,
                    {
                        "case_id": str(command.clinical_case_id),
                        "reminder_id": str(value.id),
                        "study_id": str(command.source_study_id),
                        "due_at": value.due_at.isoformat(),
                        "reason": value.reason,
                    },
                    command.actor,
                    "ECGRepeatReminder",
                )
            )
            _store_idempotency(
                uow,
                command.actor,
                "ScheduleRepeatECGReminder",
                command.idempotency_key,
                fingerprint,
                value.id,
                {"reminder_id": str(value.id)},
                now,
            )
            uow.commit()
            return value

    def acknowledge_reminder(
        self, reminder_id: UUID, actor: ActorContext, idempotency_key: str, expected_version: int
    ) -> ECGRepeatReminder:
        return self._transition_reminder(
            reminder_id, actor, idempotency_key, expected_version, None
        )

    def complete_reminder(
        self,
        reminder_id: UUID,
        study_id: UUID,
        actor: ActorContext,
        idempotency_key: str,
        expected_version: int,
    ) -> ECGRepeatReminder:
        return self._transition_reminder(
            reminder_id, actor, idempotency_key, expected_version, study_id
        )

    def _transition_reminder(
        self,
        reminder_id: UUID,
        actor: ActorContext,
        key: str,
        expected_version: int,
        study_id: UUID | None,
    ) -> ECGRepeatReminder:
        action = "CompleteRepeatECGReminder" if study_id else "AcknowledgeRepeatECGReminder"
        fingerprint = command_fingerprint(
            {
                "reminder_id": str(reminder_id),
                "study_id": str(study_id),
                "expected_version": expected_version,
            }
        )
        with self._uow() as uow:
            _validate_actor(uow, actor)
            previous = _idempotent(uow, actor, action, key, fingerprint)
            if previous:
                value = uow.ecg_clinical.get_reminder(reminder_id)
                if value is None:
                    raise ResourceConflictError("stored reminder is unavailable")
                return value
            value = uow.ecg_clinical.get_reminder(reminder_id)
            if value is None:
                raise ResourceNotFoundError("repeat ECG reminder not found")
            if value.record_version != expected_version:
                raise OptimisticConcurrencyError("repeat ECG reminder has a newer version")
            if study_id:
                study = uow.ecg_clinical.get_study(study_id)
                if study is None or study.clinical_case_id != value.clinical_case_id:
                    raise ResourceNotFoundError("completion ECG study not found")
                value.complete(study_id, utc_now(), _context(actor))
            else:
                value.acknowledge(actor.actor_id, utc_now(), _context(actor))
            uow.ecg_clinical.save_reminder(value, expected_version)
            uow.collect_events([value])
            _store_idempotency(
                uow,
                actor,
                action,
                key,
                fingerprint,
                value.id,
                {"reminder_id": str(value.id)},
                utc_now(),
            )
            uow.commit()
            return value

    def _resolve_content(self, command: IngestECG) -> bytes:
        if command.source_type is ECGSourceType.DICOM_CONNECTOR:
            if not command.external_reference:
                raise ValueError("DICOM connector reference is required")
            return self._dicom_connector.retrieve(command.external_reference)
        if command.content is None:
            raise ValueError("ECG source content is required")
        return command.content

    def _source(self, source_type: ECGSourceType) -> ECGSourceAdapter:
        key = "dicom_file" if source_type is ECGSourceType.DICOM_CONNECTOR else source_type.value
        try:
            return self._sources[key]
        except KeyError as error:
            raise ValueError("ECG source adapter is not configured") from error

    def _samples(self, study: ECGStudySnapshot) -> dict[str, tuple[float, ...]]:
        if study.normalized_waveform_artifact_id is None:
            return {}
        with self._artifacts.open(study.normalized_waveform_artifact_id) as stream:
            value = json.load(stream)
        return {
            str(item["name"]): tuple(float(sample) for sample in item["samples"])
            for item in value["leads"]
        }


class ECGQueryService:
    """Read persisted ECG projections without exposing ORM records or storage paths."""

    def __init__(
        self,
        unit_of_work: UnitOfWorkFactory,
        artifact_store: ECGArtifactStore,
        source_adapters: dict[str, ECGSourceAdapter],
        providers: dict[str, ECGAIProvider],
        dicom_connector: DICOMSourceConnector,
    ) -> None:
        self._uow = unit_of_work
        self._artifacts = artifact_store
        self._sources = source_adapters
        self._providers = providers
        self._dicom_connector = dicom_connector

    def list_studies(self, case_id: UUID) -> tuple[ECGStudySnapshot, ...]:
        with self._uow() as uow:
            if uow.cases.get(case_id) is None:
                raise ResourceNotFoundError("clinical case not found")
            return uow.ecg_clinical.list_studies(case_id)

    def get_study(self, study_id: UUID) -> ECGStudySnapshot:
        with self._uow() as uow:
            value = uow.ecg_clinical.get_study(study_id)
            if value is None:
                raise ResourceNotFoundError("ECG study not found")
            return value

    def get_quality(self, study_id: UUID) -> ECGQualityResult:
        with self._uow() as uow:
            value = uow.ecg_clinical.get_quality(study_id)
            if value is None:
                raise ResourceNotFoundError("ECG quality assessment not found")
            return value

    def waveform_document(self, study_id: UUID) -> dict[str, object]:
        with self._uow() as uow:
            study = uow.ecg_clinical.get_study(study_id)
            if study is None:
                raise ResourceNotFoundError("ECG study not found")
            if not study.waveform_available or study.normalized_waveform_artifact_id is None:
                raise ResourceConflictError("structured waveform is unavailable for this ECG study")
            artifact = uow.ecg_clinical.get_artifact(study.normalized_waveform_artifact_id)
            if artifact is None or not self._artifacts.verify(
                artifact.artifact_id, artifact.checksum_sha256
            ):
                raise ResourceConflictError("normalized waveform integrity check failed")
            with self._artifacts.open(artifact.artifact_id) as stream:
                value = json.load(stream)
            if not isinstance(value, dict):
                raise ResourceConflictError("normalized waveform artifact is malformed")
            return value

    def preview(self, study_id: UUID) -> tuple[bytes, str]:
        with self._uow() as uow:
            study = uow.ecg_clinical.get_study(study_id)
            if study is None or study.preview_artifact_id is None:
                raise ResourceNotFoundError("ECG preview not found")
            artifact = uow.ecg_clinical.get_artifact(study.preview_artifact_id)
            if artifact is None or not self._artifacts.verify(
                artifact.artifact_id, artifact.checksum_sha256
            ):
                raise ResourceConflictError("ECG preview integrity check failed")
            with self._artifacts.open(artifact.artifact_id) as stream:
                return stream.read(), artifact.content_type

    def artifacts(self, study_id: UUID) -> tuple[ArtifactMetadata, ...]:
        with self._uow() as uow:
            study = uow.ecg_clinical.get_study(study_id)
            if study is None:
                raise ResourceNotFoundError("ECG study not found")
            identifiers = (
                study.raw_artifact_id,
                study.normalized_waveform_artifact_id,
                study.preview_artifact_id,
            )
            return tuple(
                item
                for identifier in identifiers
                if identifier is not None
                and (item := uow.ecg_clinical.get_artifact(identifier)) is not None
            )

    def ingestion_job(self, job_id: UUID) -> ECGIngestionJob:
        with self._uow() as uow:
            value = uow.ecg_clinical.get_ingestion_job(job_id)
            if value is None:
                raise ResourceNotFoundError("ECG ingestion job not found")
            return value

    def analyses(self, study_id: UUID) -> tuple[ECGAnalysisSnapshot, ...]:
        with self._uow() as uow:
            if uow.ecg_clinical.get_study(study_id) is None:
                raise ResourceNotFoundError("ECG study not found")
            return uow.ecg_clinical.list_analyses(study_id)

    def analysis(self, analysis_id: UUID) -> ECGAnalysisSnapshot:
        with self._uow() as uow:
            value = uow.ecg_clinical.get_analysis(analysis_id)
            if value is None:
                raise ResourceNotFoundError("ECG analysis not found")
            return value

    def interpretations(self, study_id: UUID) -> tuple[PhysicianInterpretationSnapshot, ...]:
        with self._uow() as uow:
            return uow.ecg_clinical.list_interpretations(study_id)

    def comparisons(self, case_id: UUID) -> tuple[DynamicECGComparison, ...]:
        with self._uow() as uow:
            return uow.ecg_clinical.list_comparisons(case_id)

    def comparison(self, comparison_id: UUID) -> DynamicECGComparison:
        with self._uow() as uow:
            value = uow.ecg_clinical.get_comparison(comparison_id)
            if value is None:
                raise ResourceNotFoundError("dynamic ECG comparison not found")
            return value

    def reminders(self, case_id: UUID) -> tuple[ECGRepeatReminder, ...]:
        with self._uow() as uow:
            return uow.ecg_clinical.list_reminders(case_id)

    def workspace(self, case_id: UUID) -> ECGWorkspaceSnapshot:
        with self._uow() as uow:
            studies = uow.ecg_clinical.list_studies(case_id)
            if uow.cases.get(case_id) is None:
                raise ResourceNotFoundError("clinical case not found")
            current = studies[-1] if studies else None
            return ECGWorkspaceSnapshot(
                clinical_case_id=case_id,
                studies=studies,
                current_study=current,
                quality=uow.ecg_clinical.get_quality(current.study_id) if current else None,
                analyses=uow.ecg_clinical.list_analyses(current.study_id) if current else (),
                interpretations=uow.ecg_clinical.list_interpretations(current.study_id)
                if current
                else (),
                comparisons=uow.ecg_clinical.list_comparisons(case_id),
                reminders=uow.ecg_clinical.list_reminders(case_id),
                safety_notice="Model scores are not clinical probabilities.",
            )

    def source_health(self) -> tuple[SourceInfo, ...]:
        values = [adapter.health() for adapter in self._sources.values()]
        values.append(self._dicom_connector.health())
        return tuple(values)

    def model_info(self) -> tuple[ModelInfo, ...]:
        return tuple(provider.get_model_info() for provider in self._providers.values())

    def provider_health(self) -> tuple[AIProviderHealth, ...]:
        return tuple(provider.health() for provider in self._providers.values())


def _findings(
    scores: dict[str, float], thresholds: dict[str, float], model: object
) -> tuple[ECGFindingSnapshot, ...]:
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return tuple(
        ECGFindingSnapshot(
            finding_code=code,
            display_label=SAFE_LABELS.get(code, code),
            model_score=score,
            threshold=thresholds.get(code),
            threshold_met=score >= thresholds[code] if code in thresholds else None,
            rank=rank,
            finding_status="above_threshold"
            if code in thresholds and score >= thresholds[code]
            else "below_threshold"
            if code in thresholds
            else "threshold_unavailable",
            explanation_reference=None,
        )
        for rank, (code, score) in enumerate(ordered, 1)
    )


def _comparability_reasons(left: ECGStudySnapshot, right: ECGStudySnapshot) -> list[str]:
    reasons = []
    if not left.waveform_available or not right.waveform_available:
        reasons.append("structured_waveform_unavailable")
    if left.sampling_rate_hz != right.sampling_rate_hz:
        reasons.append("sampling_rate_mismatch")
    if left.amplitude_unit != right.amplitude_unit:
        reasons.append("amplitude_unit_mismatch")
    if left.lead_configuration != right.lead_configuration:
        reasons.append("lead_configuration_mismatch")
    if left.preprocessing_version != right.preprocessing_version:
        reasons.append("preprocessing_version_mismatch")
    return reasons


def _compare_leads(
    left: dict[str, tuple[float, ...]], right: dict[str, tuple[float, ...]]
) -> tuple[LeadComparison, ...]:
    output = []
    for name in sorted(set(left) & set(right)):
        count = min(len(left[name]), len(right[name]))
        a, b = left[name][:count], right[name][:count]
        scale = max(
            max((abs(item) for item in a), default=1.0),
            max((abs(item) for item in b), default=1.0),
            1.0,
        )
        difference = sum(abs(x - y) for x, y in zip(a, b, strict=True)) / count / scale
        mean_a, mean_b = sum(a) / count, sum(b) / count
        numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
        denominator = sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b))
        similarity = numerator / denominator if denominator else 0.0
        amplitude = (max(b) - min(b)) / max(max(a) - min(a), 1e-9)
        output.append(
            LeadComparison(
                name,
                round(similarity, 4),
                round(difference, 4),
                round(amplitude, 4),
                round((mean_b - mean_a) / scale, 4),
                0.0,
                "unchanged",
            )
        )
    return tuple(output)


def _score_deltas(
    left: tuple[ECGAnalysisSnapshot, ...], right: tuple[ECGAnalysisSnapshot, ...]
) -> tuple[tuple[str, float, float, float], ...]:
    if (
        not left
        or not right
        or left[0].model_name != right[0].model_name
        or left[0].model_version != right[0].model_version
    ):
        return ()
    before = {item.finding_code: item.model_score for item in left[0].findings}
    after = {item.finding_code: item.model_score for item in right[0].findings}
    return tuple(
        (label, before[label], after[label], round(after[label] - before[label], 6))
        for label in sorted(set(before) & set(after))
    )


def _validate_actor(uow: ECGUnitOfWork, actor: ActorContext) -> None:
    if uow.actors.role_for(actor.actor_id) is None:
        raise ResourceNotFoundError("verified clinical actor is not persisted")


def _context(actor: ActorContext) -> EventContext:
    return EventContext(
        actor.correlation_id, actor.causation_id, actor.actor_id, actor.audit_metadata()
    )


def _event(
    event_type: str,
    aggregate_id: UUID,
    version: int,
    payload: dict[str, object],
    actor: ActorContext,
    aggregate_type: str = "ECGStudy",
) -> EventEnvelope:
    return EventEnvelope.from_context(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=version,
        payload=payload,
        context=_context(actor),
    )


def _idempotent(
    uow: ECGUnitOfWork, actor: ActorContext, command_type: str, key: str, fingerprint: str
) -> IdempotencyResult | None:
    existing = uow.idempotency.lock_and_get(
        actor.actor_id, command_type, require_text(key, "idempotency_key")
    )
    if existing and existing.request_hash != fingerprint:
        raise ResourceConflictError("idempotency key was already used with a different request")
    return existing


def _store_idempotency(
    uow: ECGUnitOfWork,
    actor: ActorContext,
    command_type: str,
    key: str,
    fingerprint: str,
    resource_id: UUID,
    response: dict[str, object],
    now: datetime,
) -> None:
    uow.idempotency.add(
        IdempotencyResult(
            actor.actor_id,
            command_type,
            key,
            uuid4(),
            fingerprint,
            "ECG",
            resource_id,
            response,
            now,
        )
    )


def _safe_failure(error: Exception) -> str:
    if isinstance(error, (ValueError, FileNotFoundError, TimeoutError, ResourceConflictError)):
        return str(error)[:500]
    return "ECG operation failed; review the correlation identifier."
