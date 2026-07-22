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

from vinami.clinical_case.domain.model import CaseStatus
from vinami.clinical_case.ports.repository import ClinicalCaseRepository
from vinami.ecg.domain.clinical import (
    BLOCKING_QUALITY,
    STANDARD_12_LEADS,
    ComparabilityStatus,
    ComparisonStatus,
    DynamicECGComparison,
    DynamicECGPhysicianReview,
    ECGIngestionJob,
    ECGQualityResult,
    ECGRepeatReminder,
    ECGSourceType,
    ECGWaveform,
    LeadComparison,
    ModelScoreEvolution,
    ReminderOrigin,
    ReminderStatus,
    SignalFeatureDelta,
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
    ECGPredictionResult,
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
R18_COMPARISON_POLICY_VERSION = "r18-dynamic-ecg-technical-comparison-1.0.0"
R18_REVIEW_RECOMMENDATION = (
    "Dynamic ECG comparison is a technical and AI-assisted review aid only; "
    "physician interpretation is required before any clinical decision."
)


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
    retry_job_id: UUID | None = None
    expected_job_version: int | None = None


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
    origin: ReminderOrigin = ReminderOrigin.PHYSICIAN_REQUEST


@dataclass(frozen=True, slots=True)
class RecordComparisonReview:
    actor: ActorContext
    idempotency_key: str
    comparison_id: UUID
    review_status: str
    interpretation: str
    occurred_at: datetime
    expected_version: int
    supersedes_review_id: UUID | None = None
    correction_reason: str | None = None


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
        *,
        fallback_provider_name: str | None = None,
    ) -> None:
        self._uow = unit_of_work
        self._artifacts = artifact_store
        self._sources = source_adapters
        self._preprocessor = preprocessor
        self._quality = quality_engine
        self._providers = providers
        self._dicom_connector = dicom_connector
        self._fallback_provider_name = fallback_provider_name

    def ingest(self, command: IngestECG) -> tuple[ECGIngestionJob, ECGStudySnapshot | None]:
        payload = {
            "case_id": str(command.clinical_case_id),
            "source_type": command.source_type.value,
            "study_reference": command.study_reference,
            "acquisition_at": command.acquisition_at.isoformat(),
            "content_type": command.content_type,
            "external_reference": command.external_reference,
            "retry_job_id": str(command.retry_job_id) if command.retry_job_id else None,
        }
        fingerprint = command_fingerprint(payload)
        with self._uow() as uow:
            _validate_actor(uow, command.actor)
            command_type = "RetryECGIngestion" if command.retry_job_id else "IngestECG"
            previous = _idempotent(
                uow, command.actor, command_type, command.idempotency_key, fingerprint
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
            if command.retry_job_id is not None:
                job = uow.ecg_clinical.get_ingestion_job(command.retry_job_id)
                if job is None or job.clinical_case_id != command.clinical_case_id:
                    raise ResourceNotFoundError("ECG ingestion job not found")
                if (
                    command.expected_job_version is not None
                    and job.record_version != command.expected_job_version
                ):
                    raise OptimisticConcurrencyError("ECG ingestion job has a newer version")
                job.mark_retry(now, context)
                uow.ecg_clinical.save_ingestion_job(job)
            else:
                job = ECGIngestionJob.request(
                    clinical_case_id=case.id,
                    source_type=command.source_type,
                    requested_by=command.actor.actor_id,
                    requested_by_role=command.actor.actor_role,
                    requested_at=now,
                    request_source=command.actor.request_source,
                    idempotency_key=command.idempotency_key,
                    study_reference=command.study_reference,
                    acquisition_at=command.acquisition_at,
                    content_type=command.content_type,
                    context=context,
                    source_connector_id=command.source_connector_id,
                    external_reference=command.external_reference,
                )
                uow.ecg_clinical.add_ingestion_job(job)
            try:
                job.start(now)
                uow.ecg_clinical.save_ingestion_job(job)
                content = self._resolve_content(command, job)
                adapter = self._source(command.source_type)
                adapter.validate_source(content, command.content_type)
                if command.retry_job_id is not None and job.artifact_id is not None:
                    raw = uow.ecg_clinical.get_artifact(job.artifact_id)
                    if raw is None:
                        raise ResourceConflictError("persisted ECG source artifact is unavailable")
                else:
                    raw = self._artifacts.write(
                        content,
                        artifact_kind="raw_source",
                        content_type=command.content_type,
                        original_filename=command.original_filename,
                    )
                    uow.ecg_clinical.add_artifact(raw)
                    job.attach_source_artifact(raw.artifact_id)
                    uow.ecg_clinical.save_ingestion_job(job)
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
                    acquisition_at=parsed.acquisition_at,
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
                    command_type,
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

    def retry_ingestion(
        self,
        job_id: UUID,
        actor: ActorContext,
        idempotency_key: str,
        expected_version: int,
    ) -> tuple[ECGIngestionJob, ECGStudySnapshot | None]:
        with self._uow() as uow:
            _validate_actor(uow, actor)
            job = uow.ecg_clinical.get_ingestion_job(job_id)
            if job is None:
                raise ResourceNotFoundError("ECG ingestion job not found")
        return self.ingest(
            IngestECG(
                actor=actor,
                idempotency_key=idempotency_key,
                clinical_case_id=job.clinical_case_id,
                source_type=job.source_type,
                study_reference=job.study_reference,
                acquisition_at=job.acquisition_at,
                content=None,
                content_type=job.content_type,
                source_connector_id=job.source_connector_id,
                external_reference=job.external_reference,
                retry_job_id=job.id,
                expected_job_version=expected_version,
            )
        )

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
            input_artifact = uow.ecg_clinical.get_artifact(study.normalized_waveform_artifact_id)
            if input_artifact is None or not self._artifacts.verify(
                input_artifact.artifact_id, input_artifact.checksum_sha256
            ):
                raise ResourceConflictError("normalized ECG waveform integrity check failed")
            with self._artifacts.open(input_artifact.artifact_id) as stream:
                waveform_bytes = stream.read()
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
            provider_warning: tuple[str, ...] = ()
            prediction_request = ECGPredictionRequest(
                study.study_id,
                f"artifact://{study.normalized_waveform_artifact_id}",
                waveform_bytes=waveform_bytes,
                input_quality=study.quality_status,
                artifact_checksum=input_artifact.checksum_sha256,
            )
            try:
                result = _validated_prediction(provider, model, prediction_request, requested_at)
                if result.failure_reason:
                    status = "rejected_quality"
                findings = _findings(result.label_scores, result.thresholds, model)
                if study.quality_status in BLOCKING_QUALITY:
                    findings = ()
                warnings = provider_warning + result.warnings
                if findings and status == "completed":
                    try:
                        explanation = provider.explain(
                            ECGExplanationRequest(
                                study.study_id,
                                f"analysis://{analysis_id}",
                                findings[0].finding_code,
                                waveform_bytes=waveform_bytes,
                                input_quality=study.quality_status,
                                artifact_checksum=input_artifact.checksum_sha256,
                            )
                        )
                        warnings = warnings + (explanation.warning,)
                        if explanation.content and explanation.content_type:
                            explanation_artifact = self._artifacts.write(
                                explanation.content,
                                artifact_kind="explanation",
                                content_type=explanation.content_type,
                            )
                            uow.ecg_clinical.add_artifact(explanation_artifact)
                    except Exception as explanation_error:
                        warnings = warnings + (
                            (
                                "Explanation artifact unavailable: "
                                f"{type(explanation_error).__name__}"
                            ),
                        )
                completed_at = result.completed_at
                started_at = result.started_at
                synthetic = result.synthetic
            except TimeoutError as error:
                fallback = self._fallback_provider(command.provider_name)
                if fallback is None:
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
                else:
                    provider_warning = (
                        _provider_fallback_warning(
                            command.provider_name,
                            self._fallback_provider_name,
                            "timed out",
                        ),
                    )
                    model = fallback.get_model_info()
                    try:
                        result = _validated_prediction(
                            fallback, model, prediction_request, requested_at
                        )
                        status = _completed_or_rejected_status(result)
                        findings = _findings(result.label_scores, result.thresholds, model)
                        warnings = provider_warning + result.warnings
                        completed_at = result.completed_at
                        started_at = result.started_at
                        synthetic = result.synthetic
                    except Exception as fallback_error:
                        status, failure_category, failure_detail = (
                            "failed",
                            "provider_failure",
                            _safe_failure(fallback_error),
                        )
                        findings, warnings, completed_at, started_at, synthetic = (
                            (),
                            provider_warning,
                            utc_now(),
                            requested_at,
                            model.synthetic,
                        )
            except Exception as error:
                fallback = self._fallback_provider(command.provider_name)
                if fallback is None:
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
                else:
                    provider_warning = (
                        _provider_fallback_warning(
                            command.provider_name,
                            self._fallback_provider_name,
                            "failed",
                        ),
                    )
                    model = fallback.get_model_info()
                    try:
                        result = _validated_prediction(
                            fallback, model, prediction_request, requested_at
                        )
                        status = _completed_or_rejected_status(result)
                        findings = _findings(result.label_scores, result.thresholds, model)
                        warnings = provider_warning + result.warnings
                        completed_at = result.completed_at
                        started_at = result.started_at
                        synthetic = result.synthetic
                    except Exception as fallback_error:
                        status, failure_category, failure_detail = (
                            "failed",
                            "provider_failure",
                            _safe_failure(fallback_error),
                        )
                        findings, warnings, completed_at, started_at, synthetic = (
                            (),
                            provider_warning,
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
                input_artifact.checksum_sha256,
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
            clinical_case = uow.cases.get(command.clinical_case_id)
            if clinical_case is None:
                raise ResourceNotFoundError("clinical case not found")
            _require_active_case(clinical_case.status)
            if (
                baseline is None
                or current is None
                or baseline.clinical_case_id != command.clinical_case_id
                or current.clinical_case_id != command.clinical_case_id
            ):
                raise ResourceNotFoundError("serial ECG study not found in this case")
            baseline_waveform = uow.ecg_clinical.get_waveform(baseline.study_id)
            current_waveform = uow.ecg_clinical.get_waveform(current.study_id)
            comparability, reasons = _comparability(
                baseline, current, baseline_waveform, current_waveform
            )
            score_deltas, score_compatibility = _score_deltas(
                uow.ecg_clinical.list_analyses(baseline.study_id),
                uow.ecg_clinical.list_analyses(current.study_id),
            )
            lead_values: tuple[LeadComparison, ...] = ()
            signal_feature_deltas: tuple[SignalFeatureDelta, ...] = ()
            rhythm_indicators: tuple[str, ...] = ()
            st_t_indicators: tuple[str, ...] = ()
            indicators: tuple[str, ...]
            if comparability is ComparabilityStatus.NON_COMPARABLE:
                status = ComparisonStatus.NON_COMPARABLE
                indicators = (
                    "studies are not technically comparable",
                    "physician review required",
                )
            else:
                baseline_samples = self._samples(baseline)
                current_samples = self._samples(current)
                lead_values = _compare_leads(baseline_samples, current_samples)
                signal_feature_deltas, rhythm_indicators, st_t_indicators = (
                    _signal_feature_deltas(
                        baseline_samples,
                        current_samples,
                        baseline.sampling_rate_hz,
                        current.sampling_rate_hz,
                    )
                )
                indicators = _technical_change_indicators(
                    lead_values,
                    tuple(reasons),
                    rhythm_indicators,
                    st_t_indicators,
                    score_deltas,
                    score_compatibility,
                )
                status = (
                    ComparisonStatus.COMPLETED_WITH_WARNING
                    if _comparison_has_warning(
                        comparability,
                        lead_values,
                        rhythm_indicators,
                        st_t_indicators,
                        score_deltas,
                        score_compatibility,
                    )
                    else ComparisonStatus.COMPLETED
                )
            now = utc_now()
            value = DynamicECGComparison(
                id=uuid4(),
                clinical_case_id=command.clinical_case_id,
                baseline_study_id=baseline.study_id,
                current_study_id=current.study_id,
                comparison_policy_version=R18_COMPARISON_POLICY_VERSION,
                preprocessing_version=current.preprocessing_version or "none",
                status=status,
                comparability_status=comparability,
                comparability_reasons=tuple(reasons),
                lead_comparisons=lead_values,
                technical_change_indicators=tuple(indicators),
                signal_feature_deltas=signal_feature_deltas,
                rhythm_change_indicators=rhythm_indicators,
                st_t_change_indicators=st_t_indicators,
                model_score_deltas=score_deltas,
                quality_context=(
                    f"baseline={baseline.quality_status}; current={current.quality_status}"
                ),
                review_recommendation=R18_REVIEW_RECOMMENDATION,
                requested_by=command.actor.actor_id,
                requested_by_role=command.actor.actor_role,
                requested_at=now,
                started_at=now,
                completed_at=now,
                physician_review_status="pending",
                model_score_compatibility=score_compatibility,
                correlation_id=command.actor.correlation_id,
            )
            uow.ecg_clinical.add_comparison(value)
            uow.stage_event(
                _event(
                    "DynamicECGComparisonRequested.v1",
                    value.id,
                    1,
                    {
                        "case_id": str(command.clinical_case_id),
                        "comparison_id": str(value.id),
                        "baseline_study_id": str(baseline.study_id),
                        "current_study_id": str(current.study_id),
                    },
                    command.actor,
                    "DynamicECGComparison",
                )
            )
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
                        "rhythm_change_indicators": list(rhythm_indicators),
                        "st_t_change_indicators": list(st_t_indicators),
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

    def record_comparison_review(
        self, command: RecordComparisonReview
    ) -> DynamicECGPhysicianReview:
        command.actor.require_physician()
        fingerprint = command_fingerprint(
            {
                "comparison_id": str(command.comparison_id),
                "review_status": command.review_status,
                "interpretation": command.interpretation,
                "occurred_at": command.occurred_at.isoformat(),
                "expected_version": command.expected_version,
                "supersedes_review_id": (
                    str(command.supersedes_review_id) if command.supersedes_review_id else None
                ),
                "correction_reason": command.correction_reason,
            }
        )
        action = (
            "CorrectDynamicECGPhysicianReview"
            if command.supersedes_review_id
            else "RecordDynamicECGPhysicianReview"
        )
        with self._uow() as uow:
            _validate_actor(uow, command.actor)
            previous = _idempotent(uow, command.actor, action, command.idempotency_key, fingerprint)
            if previous:
                value = uow.ecg_clinical.get_comparison_review(
                    UUID(str(previous.response_payload["review_id"]))
                )
                if value is None:
                    raise ResourceConflictError("stored comparison review is unavailable")
                return value
            comparison = uow.ecg_clinical.get_comparison(command.comparison_id)
            if comparison is None:
                raise ResourceNotFoundError("dynamic ECG comparison not found")
            clinical_case = uow.cases.get(comparison.clinical_case_id)
            if clinical_case is None:
                raise ResourceNotFoundError("clinical case not found")
            _require_active_case(clinical_case.status)
            history = uow.ecg_clinical.list_comparison_reviews(command.comparison_id)
            current_version = history[0].record_version if history else 0
            if current_version != command.expected_version:
                raise OptimisticConcurrencyError("dynamic ECG review has a newer version")
            if command.supersedes_review_id:
                if not history or history[0].review_id != command.supersedes_review_id:
                    raise ResourceConflictError(
                        "only the latest comparison review can be corrected"
                    )
                require_text(command.correction_reason or "", "correction_reason")
            elif history:
                raise ResourceConflictError("comparison review already exists; create a correction")
            now = utc_now()
            value = DynamicECGPhysicianReview(
                review_id=uuid4(),
                comparison_id=command.comparison_id,
                actor_id=command.actor.actor_id,
                actor_role=command.actor.actor_role,
                review_status=command.review_status,
                interpretation=command.interpretation,
                occurred_at=command.occurred_at,
                recorded_at=now,
                correlation_id=command.actor.correlation_id,
                record_version=current_version + 1,
                revision_number=len(history) + 1,
                supersedes_review_id=command.supersedes_review_id,
                correction_reason=command.correction_reason,
            )
            uow.ecg_clinical.add_comparison_review(value)
            event_type = (
                "DynamicECGPhysicianReviewCorrected.v1"
                if command.supersedes_review_id
                else "DynamicECGPhysicianReviewRecorded.v1"
            )
            uow.stage_event(
                _event(
                    event_type,
                    value.review_id,
                    value.record_version,
                    {
                        "case_id": str(comparison.clinical_case_id),
                        "comparison_id": str(comparison.id),
                        "review_id": str(value.review_id),
                        "review_status": value.review_status,
                        "resulting_version": value.record_version,
                    },
                    command.actor,
                    "DynamicECGPhysicianReview",
                )
            )
            _store_idempotency(
                uow,
                command.actor,
                action,
                command.idempotency_key,
                fingerprint,
                value.review_id,
                {"review_id": str(value.review_id)},
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
            clinical_case = uow.cases.get(command.clinical_case_id)
            if clinical_case is None:
                raise ResourceNotFoundError("clinical case not found")
            _require_active_case(clinical_case.status)
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
                requested_by_role=command.actor.actor_role,
                origin=command.origin,
                updated_at=now,
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

    def cancel_reminder(
        self,
        reminder_id: UUID,
        reason: str,
        actor: ActorContext,
        idempotency_key: str,
        expected_version: int,
    ) -> ECGRepeatReminder:
        return self._transition_reminder(
            reminder_id,
            actor,
            idempotency_key,
            expected_version,
            None,
            cancellation_reason=reason,
        )

    def _transition_reminder(
        self,
        reminder_id: UUID,
        actor: ActorContext,
        key: str,
        expected_version: int,
        study_id: UUID | None,
        cancellation_reason: str | None = None,
    ) -> ECGRepeatReminder:
        action = (
            "CancelRepeatECGReminder"
            if cancellation_reason is not None
            else "CompleteRepeatECGReminder"
            if study_id
            else "AcknowledgeRepeatECGReminder"
        )
        fingerprint = command_fingerprint(
            {
                "reminder_id": str(reminder_id),
                "study_id": str(study_id),
                "expected_version": expected_version,
                "cancellation_reason": cancellation_reason,
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
            clinical_case = uow.cases.get(value.clinical_case_id)
            if clinical_case is None:
                raise ResourceNotFoundError("clinical case not found")
            _require_active_case(clinical_case.status)
            if cancellation_reason is not None:
                value.cancel(actor.actor_id, cancellation_reason, utc_now(), _context(actor))
            elif study_id:
                study = uow.ecg_clinical.get_study(study_id)
                if study is None or study.clinical_case_id != value.clinical_case_id:
                    raise ResourceNotFoundError("completion ECG study not found")
                source = uow.ecg_clinical.get_study(value.source_study_id)
                if source is None:
                    raise ResourceConflictError("source ECG study is unavailable")
                if (study.acquisition_at, study.study_id) <= (
                    source.acquisition_at,
                    source.study_id,
                ):
                    raise ResourceConflictError(
                        "repeat ECG completion requires a subsequent acquired study"
                    )
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

    def _resolve_content(self, command: IngestECG, job: ECGIngestionJob) -> bytes:
        if command.source_type is ECGSourceType.DICOM_CONNECTOR:
            if not command.external_reference:
                raise ValueError("DICOM connector reference is required")
            return self._dicom_connector.retrieve(command.external_reference, job.retry_count)
        if command.retry_job_id is not None and job.artifact_id is not None:
            with self._artifacts.open(job.artifact_id) as stream:
                return stream.read()
        if command.content is None:
            raise ValueError("ECG source content is required")
        return command.content

    def _source(self, source_type: ECGSourceType) -> ECGSourceAdapter:
        key = "dicom_file" if source_type is ECGSourceType.DICOM_CONNECTOR else source_type.value
        try:
            return self._sources[key]
        except KeyError as error:
            raise ValueError("ECG source adapter is not configured") from error

    def _fallback_provider(self, primary_name: str) -> ECGAIProvider | None:
        if self._fallback_provider_name is None or self._fallback_provider_name == primary_name:
            return None
        return self._providers.get(self._fallback_provider_name)

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

    def ingestion_jobs(self, case_id: UUID) -> tuple[ECGIngestionJob, ...]:
        with self._uow() as uow:
            if uow.cases.get(case_id) is None:
                raise ResourceNotFoundError("clinical case not found")
            return uow.ecg_clinical.list_ingestion_jobs(case_id)

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

    def explanation_artifact(self, analysis_id: UUID) -> tuple[bytes, str]:
        with self._uow() as uow:
            value = uow.ecg_clinical.get_analysis(analysis_id)
            if value is None:
                raise ResourceNotFoundError("ECG analysis not found")
            if value.explanation_artifact_id is None:
                raise ResourceNotFoundError("ECG explanation artifact not found")
            artifact = uow.ecg_clinical.get_artifact(value.explanation_artifact_id)
            if artifact is None or not self._artifacts.verify(
                artifact.artifact_id, artifact.checksum_sha256
            ):
                raise ResourceConflictError("ECG explanation artifact integrity check failed")
            with self._artifacts.open(artifact.artifact_id) as stream:
                return stream.read(), artifact.content_type

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

    def comparison_reviews(self, comparison_id: UUID) -> tuple[DynamicECGPhysicianReview, ...]:
        with self._uow() as uow:
            if uow.ecg_clinical.get_comparison(comparison_id) is None:
                raise ResourceNotFoundError("dynamic ECG comparison not found")
            return uow.ecg_clinical.list_comparison_reviews(comparison_id)

    def reminders(self, case_id: UUID) -> tuple[ECGRepeatReminder, ...]:
        with self._uow() as uow:
            values = uow.ecg_clinical.list_reminders(case_id)
            for value in values:
                value.status = value.effective_status(utc_now())
            return values

    def reminder(self, reminder_id: UUID) -> ECGRepeatReminder:
        with self._uow() as uow:
            value = uow.ecg_clinical.get_reminder(reminder_id)
            if value is None:
                raise ResourceNotFoundError("repeat ECG reminder not found")
            value.status = value.effective_status(utc_now())
            return value

    def workspace(self, case_id: UUID) -> ECGWorkspaceSnapshot:
        with self._uow() as uow:
            studies = uow.ecg_clinical.list_studies(case_id)
            if uow.cases.get(case_id) is None:
                raise ResourceNotFoundError("clinical case not found")
            current = studies[-1] if studies else None
            comparisons = uow.ecg_clinical.list_comparisons(case_id)
            comparison_reviews = tuple(
                review
                for comparison in comparisons
                for review in uow.ecg_clinical.list_comparison_reviews(comparison.id)
            )
            reminders = uow.ecg_clinical.list_reminders(case_id)
            for reminder in reminders:
                reminder.status = reminder.effective_status(utc_now())
            return ECGWorkspaceSnapshot(
                clinical_case_id=case_id,
                studies=studies,
                current_study=current,
                quality=uow.ecg_clinical.get_quality(current.study_id) if current else None,
                analyses=uow.ecg_clinical.list_analyses(current.study_id) if current else (),
                interpretations=uow.ecg_clinical.list_interpretations(current.study_id)
                if current
                else (),
                ingestion_jobs=uow.ecg_clinical.list_ingestion_jobs(case_id),
                comparisons=comparisons,
                comparison_reviews=comparison_reviews,
                reminders=reminders,
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


def _validated_prediction(
    provider: ECGAIProvider,
    model: ModelInfo,
    request: ECGPredictionRequest,
    requested_at: datetime,
) -> ECGPredictionResult:
    validation = provider.validate_input(request)
    if validation.valid:
        return provider.predict(request)
    completed_at = utc_now()
    return ECGPredictionResult(
        request.study_id,
        model.name,
        model.version,
        model.provider_name,
        requested_at,
        completed_at,
        request.input_quality,
        {},
        {},
        (),
        (),
        validation.warnings,
        {
            "input_artifact_checksum": request.artifact_checksum or "unavailable",
            "input_reference": request.input_reference,
            "validation_status": "rejected",
        },
        validation.failure_reason,
        model.synthetic,
    )


def _completed_or_rejected_status(result: ECGPredictionResult) -> str:
    return "rejected_quality" if result.failure_reason else "completed_with_warning"


def _provider_fallback_warning(primary: str, fallback: str | None, reason: str) -> str:
    return (
        f"Primary ECG provider '{primary}' {reason}; explicitly configured fallback "
        f"provider '{fallback or 'unavailable'}' was used."
    )


def _comparability(
    left: ECGStudySnapshot,
    right: ECGStudySnapshot,
    left_waveform: ECGWaveform | None,
    right_waveform: ECGWaveform | None,
) -> tuple[ComparabilityStatus, list[str]]:
    reasons: list[str] = []
    blocking = False
    if not left.waveform_available or not right.waveform_available:
        reasons.append("waveform_unavailable")
        blocking = True
    if left.sampling_rate_hz != right.sampling_rate_hz:
        reasons.append("sampling_rate_incompatible")
        blocking = True
    if left.amplitude_unit != right.amplitude_unit:
        reasons.append("units_incompatible")
        blocking = True
    if left.lead_configuration != right.lead_configuration:
        reasons.append("lead_availability_changed")
    if left.preprocessing_version != right.preprocessing_version:
        reasons.append("preprocessing_mismatch")
        blocking = True
    if left.quality_status in BLOCKING_QUALITY or right.quality_status in BLOCKING_QUALITY:
        reasons.append("poor_quality")
    left_calibration = getattr(left_waveform, "calibration", None)
    right_calibration = getattr(right_waveform, "calibration", None)
    if left_calibration and right_calibration and left_calibration != right_calibration:
        reasons.append("calibration_incompatible")
        blocking = True
    left_leads = set(getattr(left_waveform, "lead_names", ()))
    right_leads = set(getattr(right_waveform, "lead_names", ()))
    overlap = len(left_leads & right_leads)
    if left_leads and right_leads and overlap < 6:
        reasons.append("insufficient_lead_overlap")
        blocking = True
    if blocking:
        return ComparabilityStatus.NON_COMPARABLE, reasons
    if left_leads != right_leads:
        return ComparabilityStatus.PARTIALLY_COMPARABLE, reasons
    if reasons:
        return ComparabilityStatus.COMPARABLE_WITH_WARNING, reasons
    return ComparabilityStatus.COMPARABLE, reasons


def _compare_leads(
    left: dict[str, tuple[float, ...]], right: dict[str, tuple[float, ...]]
) -> tuple[LeadComparison, ...]:
    output: list[LeadComparison] = []
    for name in sorted(set(left) & set(right), key=_lead_sort_key):
        count = min(len(left[name]), len(right[name]))
        if count == 0:
            continue
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
        baseline_spread = max(max(a) - min(a), 1e-9)
        amplitude = (max(b) - min(b)) / baseline_spread
        baseline_shift = (mean_b - mean_a) / scale
        alignment = "aligned" if len(left[name]) == len(right[name]) else "truncated_to_overlap"
        quality = (
            "possible_signal_change"
            if difference >= 0.15 or abs(baseline_shift) >= 0.1 or amplitude >= 1.35
            else "possible_low_amplitude_change"
            if amplitude <= 0.75
            else "unchanged"
        )
        output.append(
            LeadComparison(
                name,
                round(similarity, 4),
                round(difference, 4),
                round(amplitude, 4),
                round(baseline_shift, 4),
                0.0,
                quality,
                alignment,
            )
        )
    return tuple(output)


def _signal_feature_deltas(
    left: dict[str, tuple[float, ...]],
    right: dict[str, tuple[float, ...]],
    left_sampling_rate_hz: float | None,
    right_sampling_rate_hz: float | None,
) -> tuple[tuple[SignalFeatureDelta, ...], tuple[str, ...], tuple[str, ...]]:
    if left_sampling_rate_hz is None or right_sampling_rate_hz is None:
        return (
            (
                SignalFeatureDelta(
                    "sampling_rate",
                    "Sampling rate",
                    left_sampling_rate_hz,
                    right_sampling_rate_hz,
                    None,
                    "Hz",
                    "unavailable",
                    "technical-comparability",
                ),
            ),
            ("rhythm proxy unavailable because sampling metadata is incomplete",),
            ("ST/T proxy unavailable because sampling metadata is incomplete",),
        )
    if left_sampling_rate_hz != right_sampling_rate_hz:
        return (
            (
                SignalFeatureDelta(
                    "sampling_rate",
                    "Sampling rate",
                    left_sampling_rate_hz,
                    right_sampling_rate_hz,
                    abs(right_sampling_rate_hz - left_sampling_rate_hz),
                    "Hz",
                    "incompatible",
                    "technical-comparability",
                ),
            ),
            ("rhythm proxy unavailable because sampling rates differ",),
            ("ST/T proxy unavailable because sampling rates differ",),
        )
    sampling_rate = left_sampling_rate_hz
    before = _extract_signal_features(left, sampling_rate)
    after = _extract_signal_features(right, sampling_rate)
    definitions = (
        ("heart_rate_proxy_bpm", "Heart-rate proxy", "beats/min", 15.0, "rhythm"),
        ("rhythm_regularity_cv", "Rhythm regularity proxy", "CV", 0.08, "rhythm"),
        ("qrs_width_proxy_ms", "QRS width proxy", "ms", 20.0, "rhythm"),
        ("st_level_proxy_uv", "ST-level morphology proxy", "uV", 75.0, "st-t"),
        ("t_wave_proxy_uv", "T-wave morphology proxy", "uV", 100.0, "st-t"),
        ("global_amplitude_proxy_uv", "Global amplitude proxy", "uV", 180.0, "technical"),
    )
    deltas: list[SignalFeatureDelta] = []
    rhythm: list[str] = []
    st_t: list[str] = []
    for name, label, unit, threshold, scope in definitions:
        previous = before.get(name)
        current = after.get(name)
        delta = abs(current - previous) if previous is not None and current is not None else None
        status = "unavailable" if delta is None else "changed" if delta >= threshold else "stable"
        deltas.append(
            SignalFeatureDelta(
                name,
                label,
                _rounded(previous),
                _rounded(current),
                _rounded(delta),
                unit,
                status,
                scope,
            )
        )
        if status != "changed":
            continue
        if scope == "rhythm":
            rhythm.append(f"possible {label.lower()} change by demonstration technical policy")
        elif scope == "st-t":
            st_t.append(f"possible {label.lower()} change by demonstration technical policy")
    if not rhythm and before.get("r_peak_count") is None:
        rhythm.append("rhythm proxy unavailable because R-peak detection was insufficient")
    if not st_t and before.get("r_peak_count") is None:
        st_t.append("ST/T proxy unavailable because R-peak detection was insufficient")
    return tuple(deltas), tuple(rhythm), tuple(st_t)


def _extract_signal_features(
    samples_by_lead: dict[str, tuple[float, ...]], sampling_rate_hz: float
) -> dict[str, float | None]:
    reference = _reference_lead(samples_by_lead)
    if reference is None:
        return {
            "r_peak_count": None,
            "heart_rate_proxy_bpm": None,
            "rhythm_regularity_cv": None,
            "qrs_width_proxy_ms": None,
            "st_level_proxy_uv": None,
            "t_wave_proxy_uv": None,
            "global_amplitude_proxy_uv": _global_amplitude(samples_by_lead),
        }
    peaks = _r_peak_indices(reference, sampling_rate_hz)
    return {
        "r_peak_count": float(len(peaks)),
        "heart_rate_proxy_bpm": _heart_rate(peaks, sampling_rate_hz),
        "rhythm_regularity_cv": _rhythm_cv(peaks),
        "qrs_width_proxy_ms": _qrs_width(reference, peaks, sampling_rate_hz),
        "st_level_proxy_uv": _segment_proxy(samples_by_lead, peaks, sampling_rate_hz, 0.08, 0.16),
        "t_wave_proxy_uv": _segment_proxy(samples_by_lead, peaks, sampling_rate_hz, 0.22, 0.38),
        "global_amplitude_proxy_uv": _global_amplitude(samples_by_lead),
    }


def _reference_lead(samples_by_lead: dict[str, tuple[float, ...]]) -> tuple[float, ...] | None:
    for name in ("II", "I", "V5", "V2"):
        if samples_by_lead.get(name):
            return samples_by_lead[name]
    return next(iter(samples_by_lead.values()), None)


def _r_peak_indices(samples: tuple[float, ...], sampling_rate_hz: float) -> tuple[int, ...]:
    if len(samples) < 3:
        return ()
    centered = tuple(value - _mean(samples) for value in samples)
    absolute = tuple(abs(value) for value in centered)
    peak = max(absolute, default=0.0)
    if peak <= 1e-9:
        return ()
    threshold = max(peak * 0.48, 75.0)
    refractory = max(1, int(0.25 * sampling_rate_hz))
    candidates = [
        index
        for index in range(1, len(absolute) - 1)
        if absolute[index] >= threshold
        and absolute[index] >= absolute[index - 1]
        and absolute[index] >= absolute[index + 1]
    ]
    selected: list[int] = []
    for candidate in candidates:
        if not selected or candidate - selected[-1] > refractory:
            selected.append(candidate)
            continue
        if absolute[candidate] > absolute[selected[-1]]:
            selected[-1] = candidate
    return tuple(selected)


def _heart_rate(peaks: tuple[int, ...], sampling_rate_hz: float) -> float | None:
    intervals = _peak_intervals(peaks)
    if not intervals:
        return None
    mean_interval = _mean(tuple(float(item) for item in intervals))
    return 60.0 / (mean_interval / sampling_rate_hz) if mean_interval else None


def _rhythm_cv(peaks: tuple[int, ...]) -> float | None:
    intervals = _peak_intervals(peaks)
    if len(intervals) < 2:
        return None
    values = tuple(float(item) for item in intervals)
    average = _mean(values)
    if average <= 0:
        return None
    variance = sum((item - average) ** 2 for item in values) / len(values)
    return sqrt(variance) / average


def _qrs_width(
    samples: tuple[float, ...], peaks: tuple[int, ...], sampling_rate_hz: float
) -> float | None:
    if not peaks:
        return None
    baseline = _mean(samples)
    widths: list[float] = []
    for peak in peaks:
        height = abs(samples[peak] - baseline)
        if height <= 1e-9:
            continue
        threshold = height * 0.5
        left = peak
        while left > 0 and abs(samples[left] - baseline) >= threshold:
            left -= 1
        right = peak
        while right < len(samples) - 1 and abs(samples[right] - baseline) >= threshold:
            right += 1
        widths.append(((right - left) / sampling_rate_hz) * 1000.0)
    return _mean(tuple(widths)) if widths else None


def _segment_proxy(
    samples_by_lead: dict[str, tuple[float, ...]],
    peaks: tuple[int, ...],
    sampling_rate_hz: float,
    start_seconds: float,
    end_seconds: float,
) -> float | None:
    if not peaks:
        return None
    values: list[float] = []
    for lead_name in STANDARD_12_LEADS:
        samples = samples_by_lead.get(lead_name)
        if not samples:
            continue
        for peak in peaks:
            baseline_start = max(0, peak - int(0.2 * sampling_rate_hz))
            baseline_end = max(0, peak - int(0.06 * sampling_rate_hz))
            segment_start = peak + int(start_seconds * sampling_rate_hz)
            segment_end = peak + int(end_seconds * sampling_rate_hz)
            if baseline_end <= baseline_start or segment_end >= len(samples):
                continue
            baseline = _mean(samples[baseline_start:baseline_end])
            segment = _mean(samples[segment_start:segment_end])
            values.append(segment - baseline)
    if not values:
        return None
    return _mean(tuple(abs(item) for item in values))


def _global_amplitude(samples_by_lead: dict[str, tuple[float, ...]]) -> float | None:
    amplitudes = tuple(max(values) - min(values) for values in samples_by_lead.values() if values)
    return _mean(amplitudes) if amplitudes else None


def _technical_change_indicators(
    lead_values: tuple[LeadComparison, ...],
    comparability_reasons: tuple[str, ...],
    rhythm_indicators: tuple[str, ...],
    st_t_indicators: tuple[str, ...],
    score_deltas: tuple[ModelScoreEvolution, ...],
    score_compatibility: str,
) -> tuple[str, ...]:
    indicators: list[str] = []
    if comparability_reasons:
        indicators.append("technical comparability warning: " + ", ".join(comparability_reasons))
    changed_leads = tuple(
        item.lead_name for item in lead_values if item.quality_difference != "unchanged"
    )
    if len(changed_leads) >= 2:
        indicators.append(
            "multiple lead-level waveform changes detected: " + ", ".join(changed_leads[:6])
        )
    elif changed_leads:
        indicators.append("lead-level waveform change detected: " + changed_leads[0])
    indicators.extend(rhythm_indicators)
    indicators.extend(st_t_indicators)
    if score_compatibility == "compatible":
        shifted = tuple(
            item.finding_code for item in score_deltas if abs(item.absolute_delta) >= 0.2
        )
        threshold_changed = tuple(
            item.finding_code for item in score_deltas if item.threshold_state_changed is True
        )
        if shifted:
            indicators.append(
                "model-score delta >= 0.20 for labels: " + ", ".join(shifted)
            )
        if threshold_changed:
            indicators.append(
                "model threshold state changed for labels: " + ", ".join(threshold_changed)
            )
    elif score_compatibility != "analysis_unavailable":
        indicators.append(f"model-score comparison unavailable: {score_compatibility}")
    if not indicators:
        indicators.append("no material technical ECG change detected by demonstration policy")
    indicators.append("physician review required before clinical use")
    return tuple(dict.fromkeys(indicators))


def _comparison_has_warning(
    comparability: ComparabilityStatus,
    lead_values: tuple[LeadComparison, ...],
    rhythm_indicators: tuple[str, ...],
    st_t_indicators: tuple[str, ...],
    score_deltas: tuple[ModelScoreEvolution, ...],
    score_compatibility: str,
) -> bool:
    return (
        comparability is not ComparabilityStatus.COMPARABLE
        or any(item.quality_difference != "unchanged" for item in lead_values)
        or bool(rhythm_indicators)
        or bool(st_t_indicators)
        or score_compatibility not in {"compatible", "analysis_unavailable"}
        or any(abs(item.absolute_delta) >= 0.2 for item in score_deltas)
        or any(item.threshold_state_changed is True for item in score_deltas)
    )


def _peak_intervals(peaks: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(right - left for left, right in zip(peaks, peaks[1:], strict=False))


def _lead_sort_key(name: str) -> tuple[int, str]:
    return (
        STANDARD_12_LEADS.index(name) if name in STANDARD_12_LEADS else len(STANDARD_12_LEADS),
        name,
    )


def _mean(values: tuple[float, ...]) -> float:
    return sum(values) / len(values) if values else 0.0


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _score_deltas(
    left: tuple[ECGAnalysisSnapshot, ...], right: tuple[ECGAnalysisSnapshot, ...]
) -> tuple[tuple[ModelScoreEvolution, ...], str]:
    if not left or not right:
        return (), "analysis_unavailable"
    if left[0].model_name != right[0].model_name:
        return (), "model_family_mismatch"
    if left[0].model_version != right[0].model_version:
        return (), "model_version_mismatch"
    if left[0].preprocessing_version != right[0].preprocessing_version:
        return (), "preprocessing_mismatch"
    if left[0].label_mapping_version != right[0].label_mapping_version:
        return (), "label_mapping_mismatch"
    before = {item.finding_code: item.model_score for item in left[0].findings}
    after = {item.finding_code: item.model_score for item in right[0].findings}
    before_findings = {item.finding_code: item for item in left[0].findings}
    after_findings = {item.finding_code: item for item in right[0].findings}
    if set(before) != set(after):
        return (), "label_mapping_mismatch"
    values = tuple(
        ModelScoreEvolution(
            finding_code=label,
            previous_score=before[label],
            current_score=after[label],
            absolute_delta=round(after[label] - before[label], 6),
            previous_threshold_met=before_findings[label].threshold_met,
            current_threshold_met=after_findings[label].threshold_met,
            threshold_state_changed=(
                before_findings[label].threshold_met != after_findings[label].threshold_met
                if before_findings[label].threshold_met is not None
                and after_findings[label].threshold_met is not None
                else None
            ),
            previous_model_version=left[0].model_version,
            current_model_version=right[0].model_version,
            compatibility_status="compatible",
        )
        for label in sorted(before)
    )
    return values, "compatible"


def _require_active_case(status: CaseStatus) -> None:
    if status is CaseStatus.CLOSED:
        raise ResourceConflictError("closed clinical case does not accept ECG commands")


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
    if isinstance(
        error,
        (ValueError, FileNotFoundError, TimeoutError, ConnectionError, ResourceConflictError),
    ):
        return str(error)[:500]
    return "ECG operation failed; review the correlation identifier."
