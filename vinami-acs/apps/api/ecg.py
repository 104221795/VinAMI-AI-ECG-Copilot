"""Versioned FastAPI delivery adapter for the R3 ECG vertical slice."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field

from apps.api.http import AuthorizedIdentity, CommandHeaders, authorize_for, command_headers_for
from vinami.ecg.adapters.artifact_store import ArtifactValidationError
from vinami.ecg.adapters.ingestion import UnsupportedECGSourceError
from vinami.ecg.application.service import (
    IngestECG,
    RecordComparisonReview,
    RecordInterpretation,
    RequestAnalysis,
    RequestComparison,
    ScheduleReminder,
)
from vinami.ecg.domain.clinical import ECGSourceType, ReminderOrigin
from vinami.ecg.ports.repository import (
    ECGAnalysisSnapshot,
    ECGFindingSnapshot,
    ECGStudySnapshot,
    PhysicianInterpretationSnapshot,
)
from vinami.identity.domain.security import Permission
from vinami.shared.container import AppContainer
from vinami.shared.domain import utc_now

router = APIRouter(prefix="/api/v1")


class ArtifactResponse(BaseModel):
    artifact_id: UUID
    artifact_kind: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    state: str
    created_at: datetime
    original_filename: str | None


class ECGStudyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    study_id: UUID
    clinical_case_id: UUID
    encounter_id: UUID
    study_reference: str
    source_type: str
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
    source_format: str
    source_content_type: str
    artifact_checksum: str
    artifact_size: int
    parser_version: str
    preprocessing_version: str | None
    quality_status: str
    aggregate_version: int
    waveform_available: bool


class QualityResponse(BaseModel):
    status: str
    reason_codes: list[str]
    affected_leads: list[str]
    parser_warnings: list[str]
    preprocessing_warnings: list[str]
    quality_engine_version: str
    assessed_at: datetime
    suppress_score_emphasis: bool


class IngestionJobResponse(BaseModel):
    ingestion_job_id: UUID
    clinical_case_id: UUID
    source_type: str
    source_connector_id: str | None
    external_reference: str | None
    status: str
    requested_by_actor_role: str
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    request_source: str
    study_reference: str
    acquisition_at: datetime
    content_type: str
    artifact_id: UUID | None
    resulting_study_id: UUID | None
    parser_name: str | None
    parser_version: str | None
    warnings: list[str]
    failure_category: str | None
    failure_detail_safe: str | None
    retry_count: int
    retry_of_job_id: UUID | None
    correlation_id: UUID
    record_version: int


class FindingResponse(BaseModel):
    finding_code: str
    display_label: str
    model_score: float
    threshold: float | None
    threshold_met: bool | None
    rank: int
    finding_status: str
    explanation_reference: str | None


class AnalysisResponse(BaseModel):
    analysis_id: UUID
    ecg_study_id: UUID
    provider_name: str
    provider_version: str
    model_name: str
    model_version: str
    model_checksum: str | None
    preprocessing_version: str
    threshold_version: str | None
    status: str
    quality_status: str
    requested_at: datetime
    completed_at: datetime | None
    inference_duration_ms: int | None
    findings: list[FindingResponse]
    warnings: list[str]
    explanation_status: str
    explanation_artifact_id: UUID | None
    failure_category: str | None
    failure_detail_safe: str | None
    correlation_id: UUID
    record_version: int
    synthetic: bool
    safety_notice: str = "Model scores are not clinical probabilities."


class RequestAnalysisBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_name: str = Field(default="mock", min_length=1, max_length=120)


class InterpretationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: UUID | None = None
    interpretation_status: str = Field(min_length=1, max_length=80)
    structured_interpretation: str = Field(min_length=1, max_length=12000)
    agreement_status: str = Field(min_length=1, max_length=80)
    disagreement_reason: str | None = Field(default=None, min_length=1, max_length=4000)
    quality_disposition: str = Field(min_length=1, max_length=80)
    repeat_ecg_requested: bool = False
    note: str | None = Field(default=None, min_length=1, max_length=8000)
    occurred_at: datetime
    expected_version: int = Field(ge=0)


class CorrectionBody(InterpretationBody):
    correction_reason: str = Field(min_length=1, max_length=2000)


class InterpretationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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


class ComparisonBody(BaseModel):
    baseline_study_id: UUID
    current_study_id: UUID


class LeadComparisonResponse(BaseModel):
    lead_name: str
    waveform_similarity: float
    normalized_difference: float
    amplitude_scale_change: float
    baseline_shift_indicator: float
    missing_data_percentage: float
    quality_difference: str
    sample_alignment_status: str


class ModelScoreEvolutionResponse(BaseModel):
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


class SignalFeatureDeltaResponse(BaseModel):
    feature_name: str
    display_label: str
    previous_value: float | None
    current_value: float | None
    absolute_delta: float | None
    unit: str | None
    status: str
    evidence_scope: str


class ComparisonResponse(BaseModel):
    comparison_id: UUID
    clinical_case_id: UUID
    baseline_study_id: UUID
    current_study_id: UUID
    comparison_policy_version: str
    preprocessing_version: str
    status: str
    comparability_status: str
    comparability_reasons: list[str]
    lead_comparisons: list[LeadComparisonResponse]
    technical_change_indicators: list[str]
    signal_feature_deltas: list[SignalFeatureDeltaResponse]
    rhythm_change_indicators: list[str]
    st_t_change_indicators: list[str]
    model_score_deltas: list[ModelScoreEvolutionResponse]
    model_score_compatibility: str
    quality_context: str
    review_recommendation: str
    requested_by_actor_role: str
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime
    physician_review_status: str
    correlation_id: UUID
    record_version: int
    safety_notice: str = "Technical ECG change indicator - physician interpretation required."


class ReminderBody(BaseModel):
    source_study_id: UUID
    reason: str = Field(min_length=1, max_length=2000)
    due_at: datetime
    origin: ReminderOrigin = ReminderOrigin.PHYSICIAN_REQUEST


class ReminderTransitionBody(BaseModel):
    expected_version: int = Field(ge=1)
    completed_study_id: UUID | None = None
    cancellation_reason: str | None = Field(default=None, min_length=1, max_length=2000)


class ReminderResponse(BaseModel):
    reminder_id: UUID
    clinical_case_id: UUID
    source_study_id: UUID
    requested_by: UUID
    requested_by_actor_role: str
    origin: str
    reason: str
    due_at: datetime
    status: str
    acknowledged_by: UUID | None
    acknowledged_at: datetime | None
    completed_study_id: UUID | None
    completed_at: datetime | None
    cancelled_by: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
    correlation_id: UUID
    record_version: int


class ConnectorResponse(BaseModel):
    connector_id: str
    display_name: str
    source_type: str
    available: bool
    capabilities: list[str]
    detail: str
    connector_type: str
    profile: str | None
    version: str | None


class ComparisonReviewBody(BaseModel):
    review_status: str = Field(min_length=1, max_length=80)
    interpretation: str = Field(min_length=1, max_length=12000)
    occurred_at: datetime
    expected_version: int = Field(ge=0)


class ComparisonReviewCorrectionBody(ComparisonReviewBody):
    correction_reason: str = Field(min_length=1, max_length=2000)


class ComparisonReviewResponse(BaseModel):
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
    supersedes_review_id: UUID | None
    correction_reason: str | None


class RetryIngestionBody(BaseModel):
    expected_version: int = Field(ge=1)


class WaveformLeadResponse(BaseModel):
    name: str
    samples: list[float]


class WaveformResponse(BaseModel):
    schema_version: str
    study_reference: str
    sampling_rate_hz: float
    amplitude_unit: str
    source_amplitude_unit: str
    conversion_method: str | None
    preprocessing_version: str
    lead_order: list[str]
    leads: list[WaveformLeadResponse]


class ECGWorkspaceResponse(BaseModel):
    clinical_case_id: UUID
    studies: list[ECGStudyResponse]
    current_study: ECGStudyResponse | None
    quality: QualityResponse | None
    analyses: list[AnalysisResponse]
    interpretations: list[InterpretationResponse]
    ingestion_jobs: list[IngestionJobResponse]
    comparisons: list[ComparisonResponse]
    comparison_reviews: list[ComparisonReviewResponse]
    reminders: list[ReminderResponse]
    capabilities: dict[str, bool]
    data_freshness: datetime
    safety_notice: str


class ImportBody(BaseModel):
    source_type: ECGSourceType
    source_connector_id: str
    external_reference: str
    study_reference: str
    acquisition_at: datetime
    expected_case_version: int | None = Field(default=None, ge=1)


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


Container = Annotated[AppContainer, Depends(_container)]
ECGRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.ECG_READ))]
ECGWrite = Annotated[CommandHeaders, Depends(command_headers_for(Permission.ECG_WRITE))]
ECGInterpret = Annotated[CommandHeaders, Depends(command_headers_for(Permission.ECG_INTERPRET))]


@router.post(
    "/clinical-cases/{case_id}/ecg-studies",
    response_model=IngestionJobResponse,
    status_code=201,
    tags=["ecg-studies"],
)
async def create_ecg_study(
    case_id: UUID,
    headers: ECGWrite,
    container: Container,
    source_type: Annotated[ECGSourceType, Form()],
    study_reference: Annotated[str, Form(min_length=1, max_length=240)],
    acquisition_at: Annotated[datetime, Form()],
    content_type: Annotated[str, Form(min_length=1, max_length=160)],
    expected_case_version: Annotated[int | None, Form(ge=1)] = None,
    artifact: Annotated[UploadFile | None, File()] = None,
) -> IngestionJobResponse:
    if artifact is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "artifact file is required")
    if (
        artifact.content_type
        and artifact.content_type.split(";", 1)[0] != content_type.split(";", 1)[0]
    ):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "declared content type does not match upload metadata",
        )
    content = await artifact.read(container.settings.ecg_artifact_max_bytes + 1)
    if len(content) > container.settings.ecg_artifact_max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "ECG artifact exceeds the configured size limit",
        )
    try:
        job, _ = container.ecg_application().ingest(
            IngestECG(
                headers.actor,
                headers.idempotency_key,
                case_id,
                source_type,
                study_reference,
                acquisition_at,
                content,
                content_type,
                artifact.filename,
                expected_case_version=expected_case_version,
            )
        )
    except ArtifactValidationError as error:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(error)) from error
    except UnsupportedECGSourceError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return _job(job)


@router.post(
    "/clinical-cases/{case_id}/ecg-imports",
    response_model=IngestionJobResponse,
    status_code=201,
    tags=["ecg-integration"],
)
def import_ecg(
    case_id: UUID, body: ImportBody, headers: ECGWrite, container: Container
) -> IngestionJobResponse:
    if body.source_type is not ECGSourceType.DICOM_CONNECTOR:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "only the configured DICOM connector is supported by this endpoint",
        )
    try:
        job, _ = container.ecg_application().ingest(
            IngestECG(
                headers.actor,
                headers.idempotency_key,
                case_id,
                body.source_type,
                body.study_reference,
                body.acquisition_at,
                None,
                "application/dicom",
                source_connector_id=body.source_connector_id,
                external_reference=body.external_reference,
                expected_case_version=body.expected_case_version,
            )
        )
    except TimeoutError as error:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, str(error)) from error
    except ConnectionError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except UnsupportedECGSourceError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return _job(job)


@router.get(
    "/clinical-cases/{case_id}/ecg-imports",
    response_model=list[IngestionJobResponse],
    tags=["ecg-integration"],
)
def list_ecg_imports(
    case_id: UUID, _auth: ECGRead, container: Container
) -> list[IngestionJobResponse]:
    return [_job(value) for value in container.ecg_queries().ingestion_jobs(case_id)]


@router.get(
    "/clinical-cases/{case_id}/ecg-studies",
    response_model=list[ECGStudyResponse],
    tags=["ecg-studies"],
)
def list_studies(case_id: UUID, _auth: ECGRead, container: Container) -> list[ECGStudyResponse]:
    return [_study(value) for value in container.ecg_queries().list_studies(case_id)]


@router.get("/ecg-studies/{study_id}", response_model=ECGStudyResponse, tags=["ecg-studies"])
def get_study(study_id: UUID, _auth: ECGRead, container: Container) -> ECGStudyResponse:
    return _study(container.ecg_queries().get_study(study_id))


@router.get(
    "/ecg-studies/{study_id}/quality",
    response_model=QualityResponse,
    tags=["ecg-studies"],
)
def get_quality(study_id: UUID, _auth: ECGRead, container: Container) -> QualityResponse:
    return _quality(container.ecg_queries().get_quality(study_id))


@router.get(
    "/ecg-studies/{study_id}/waveform",
    response_model=WaveformResponse,
    tags=["ecg-studies"],
)
def get_waveform(study_id: UUID, _auth: ECGRead, container: Container) -> WaveformResponse:
    return WaveformResponse.model_validate(container.ecg_queries().waveform_document(study_id))


@router.get("/ecg-studies/{study_id}/preview", response_class=Response, tags=["ecg-studies"])
def get_preview(study_id: UUID, _auth: ECGRead, container: Container) -> Response:
    content, content_type = container.ecg_queries().preview(study_id)
    return Response(
        content,
        media_type=content_type,
        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
    )


@router.get(
    "/ecg-studies/{study_id}/artifacts", response_model=list[ArtifactResponse], tags=["ecg-studies"]
)
def get_artifacts(study_id: UUID, _auth: ECGRead, container: Container) -> list[ArtifactResponse]:
    return [
        ArtifactResponse.model_validate(value, from_attributes=True)
        for value in container.ecg_queries().artifacts(study_id)
    ]


@router.get(
    "/ecg-ingestion-jobs/{job_id}", response_model=IngestionJobResponse, tags=["ecg-integration"]
)
def get_ingestion(job_id: UUID, _auth: ECGRead, container: Container) -> IngestionJobResponse:
    return _job(container.ecg_queries().ingestion_job(job_id))


@router.post(
    "/ecg-ingestion-jobs/{job_id}/retry",
    response_model=IngestionJobResponse,
    tags=["ecg-integration"],
)
def retry_ingestion(
    job_id: UUID,
    body: RetryIngestionBody,
    headers: ECGWrite,
    container: Container,
) -> IngestionJobResponse:
    try:
        job, _ = container.ecg_application().retry_ingestion(
            job_id, headers.actor, headers.idempotency_key, body.expected_version
        )
    except TimeoutError as error:
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, str(error)) from error
    except ConnectionError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except UnsupportedECGSourceError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    return _job(job)


@router.get(
    "/ecg-source-connectors", response_model=list[ConnectorResponse], tags=["ecg-integration"]
)
def source_connectors(_auth: ECGRead, container: Container) -> list[ConnectorResponse]:
    return [
        ConnectorResponse(
            connector_id=value.connector_id,
            display_name=value.display_name,
            source_type=value.source_type,
            available=value.available,
            capabilities=list(value.capabilities),
            detail=value.detail,
            connector_type=value.connector_type,
            profile=value.profile,
            version=value.version,
        )
        for value in container.ecg_queries().source_health()
    ]


@router.get(
    "/ecg-source-connectors/{connector_id}/health",
    response_model=ConnectorResponse,
    tags=["ecg-integration"],
)
def source_connector_health(
    connector_id: str, _auth: ECGRead, container: Container
) -> ConnectorResponse:
    values = source_connectors(_auth, container)
    for value in values:
        if value.connector_id == connector_id:
            return value
    raise HTTPException(status.HTTP_404_NOT_FOUND, "ECG source connector not found")


@router.post(
    "/ecg-studies/{study_id}/analyses",
    response_model=AnalysisResponse,
    status_code=201,
    tags=["ecg-ai"],
)
def request_analysis(
    study_id: UUID, body: RequestAnalysisBody, headers: ECGWrite, container: Container
) -> AnalysisResponse:
    return _analysis(
        container.ecg_application().request_analysis(
            RequestAnalysis(headers.actor, headers.idempotency_key, study_id, body.provider_name)
        )
    )


@router.get(
    "/ecg-studies/{study_id}/analyses", response_model=list[AnalysisResponse], tags=["ecg-ai"]
)
def list_analyses(study_id: UUID, _auth: ECGRead, container: Container) -> list[AnalysisResponse]:
    return [_analysis(value) for value in container.ecg_queries().analyses(study_id)]


@router.get(
    "/ecg-studies/{study_id}/analyses/latest",
    response_model=AnalysisResponse | None,
    tags=["ecg-ai"],
)
def latest_analysis(
    study_id: UUID, _auth: ECGRead, container: Container
) -> AnalysisResponse | None:
    values = container.ecg_queries().analyses(study_id)
    return _analysis(values[0]) if values else None


@router.get("/ecg-analyses/{analysis_id}", response_model=AnalysisResponse, tags=["ecg-ai"])
def get_analysis(analysis_id: UUID, _auth: ECGRead, container: Container) -> AnalysisResponse:
    return _analysis(container.ecg_queries().analysis(analysis_id))


@router.get(
    "/ecg-analyses/{analysis_id}/explanation",
    response_class=Response,
    tags=["ecg-ai"],
)
def get_analysis_explanation(analysis_id: UUID, _auth: ECGRead, container: Container) -> Response:
    content, content_type = container.ecg_queries().explanation_artifact(analysis_id)
    content_security_policy = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    return Response(
        content,
        media_type=content_type,
        headers={"Content-Security-Policy": content_security_policy},
    )


@router.post(
    "/ecg-analyses/{analysis_id}/retry",
    response_model=AnalysisResponse,
    status_code=201,
    tags=["ecg-ai"],
)
def retry_analysis(
    analysis_id: UUID, body: RequestAnalysisBody, headers: ECGWrite, container: Container
) -> AnalysisResponse:
    previous = container.ecg_queries().analysis(analysis_id)
    return _analysis(
        container.ecg_application().request_analysis(
            RequestAnalysis(
                headers.actor, headers.idempotency_key, previous.ecg_study_id, body.provider_name
            )
        )
    )


@router.post(
    "/ecg-studies/{study_id}/physician-interpretations",
    response_model=InterpretationResponse,
    status_code=201,
    tags=["ecg-review"],
)
def record_interpretation(
    study_id: UUID, body: InterpretationBody, headers: ECGInterpret, container: Container
) -> InterpretationResponse:
    return _interpretation(
        container.ecg_application().record_interpretation(
            _interpretation_command(study_id, body, headers)
        )
    )


@router.get(
    "/ecg-studies/{study_id}/physician-interpretations",
    response_model=list[InterpretationResponse],
    tags=["ecg-review"],
)
def list_interpretations(
    study_id: UUID, _auth: ECGRead, container: Container
) -> list[InterpretationResponse]:
    return [_interpretation(value) for value in container.ecg_queries().interpretations(study_id)]


@router.post(
    "/ecg-studies/{study_id}/physician-interpretations/{interpretation_id}/corrections",
    response_model=InterpretationResponse,
    status_code=201,
    tags=["ecg-review"],
)
def correct_interpretation(
    study_id: UUID,
    interpretation_id: UUID,
    body: CorrectionBody,
    headers: ECGInterpret,
    container: Container,
) -> InterpretationResponse:
    command = _interpretation_command(
        study_id, body, headers, interpretation_id, body.correction_reason
    )
    return _interpretation(container.ecg_application().record_interpretation(command))


@router.post(
    "/clinical-cases/{case_id}/ecg-comparisons",
    response_model=ComparisonResponse,
    status_code=201,
    tags=["dynamic-ecg"],
)
def create_comparison(
    case_id: UUID, body: ComparisonBody, headers: ECGWrite, container: Container
) -> ComparisonResponse:
    return _comparison(
        container.ecg_application().compare(
            RequestComparison(
                headers.actor,
                headers.idempotency_key,
                case_id,
                body.baseline_study_id,
                body.current_study_id,
            )
        )
    )


@router.get(
    "/clinical-cases/{case_id}/ecg-comparisons",
    response_model=list[ComparisonResponse],
    tags=["dynamic-ecg"],
)
def list_comparisons(
    case_id: UUID, _auth: ECGRead, container: Container
) -> list[ComparisonResponse]:
    return [_comparison(value) for value in container.ecg_queries().comparisons(case_id)]


@router.get(
    "/ecg-comparisons/{comparison_id}", response_model=ComparisonResponse, tags=["dynamic-ecg"]
)
def get_comparison(comparison_id: UUID, _auth: ECGRead, container: Container) -> ComparisonResponse:
    return _comparison(container.ecg_queries().comparison(comparison_id))


@router.post(
    "/ecg-comparisons/{comparison_id}/physician-reviews",
    response_model=ComparisonReviewResponse,
    status_code=201,
    tags=["dynamic-ecg"],
)
def record_comparison_review(
    comparison_id: UUID,
    body: ComparisonReviewBody,
    headers: ECGInterpret,
    container: Container,
) -> ComparisonReviewResponse:
    return _comparison_review(
        container.ecg_application().record_comparison_review(
            RecordComparisonReview(
                actor=headers.actor,
                idempotency_key=headers.idempotency_key,
                comparison_id=comparison_id,
                review_status=body.review_status,
                interpretation=body.interpretation,
                occurred_at=body.occurred_at,
                expected_version=body.expected_version,
            )
        )
    )


@router.get(
    "/ecg-comparisons/{comparison_id}/physician-reviews",
    response_model=list[ComparisonReviewResponse],
    tags=["dynamic-ecg"],
)
def list_comparison_reviews(
    comparison_id: UUID, _auth: ECGRead, container: Container
) -> list[ComparisonReviewResponse]:
    return [
        _comparison_review(value)
        for value in container.ecg_queries().comparison_reviews(comparison_id)
    ]


@router.post(
    "/ecg-comparisons/{comparison_id}/physician-reviews/{review_id}/corrections",
    response_model=ComparisonReviewResponse,
    status_code=201,
    tags=["dynamic-ecg"],
)
def correct_comparison_review(
    comparison_id: UUID,
    review_id: UUID,
    body: ComparisonReviewCorrectionBody,
    headers: ECGInterpret,
    container: Container,
) -> ComparisonReviewResponse:
    return _comparison_review(
        container.ecg_application().record_comparison_review(
            RecordComparisonReview(
                actor=headers.actor,
                idempotency_key=headers.idempotency_key,
                comparison_id=comparison_id,
                review_status=body.review_status,
                interpretation=body.interpretation,
                occurred_at=body.occurred_at,
                expected_version=body.expected_version,
                supersedes_review_id=review_id,
                correction_reason=body.correction_reason,
            )
        )
    )


@router.get(
    "/clinical-cases/{case_id}/ecg-evolution",
    response_model=list[ComparisonResponse],
    tags=["dynamic-ecg"],
)
def get_evolution(case_id: UUID, _auth: ECGRead, container: Container) -> list[ComparisonResponse]:
    return list_comparisons(case_id, _auth, container)


@router.post(
    "/clinical-cases/{case_id}/repeat-ecg-reminders",
    response_model=ReminderResponse,
    status_code=201,
    tags=["ecg-reminders"],
)
def schedule_reminder(
    case_id: UUID, body: ReminderBody, headers: ECGWrite, container: Container
) -> ReminderResponse:
    return _reminder(
        container.ecg_application().schedule_reminder(
            ScheduleReminder(
                headers.actor,
                headers.idempotency_key,
                case_id,
                body.source_study_id,
                body.reason,
                body.due_at,
                body.origin,
            )
        )
    )


@router.get(
    "/clinical-cases/{case_id}/repeat-ecg-reminders",
    response_model=list[ReminderResponse],
    tags=["ecg-reminders"],
)
def list_reminders(case_id: UUID, _auth: ECGRead, container: Container) -> list[ReminderResponse]:
    return [_reminder(value) for value in container.ecg_queries().reminders(case_id)]


@router.get(
    "/repeat-ecg-reminders/{reminder_id}",
    response_model=ReminderResponse,
    tags=["ecg-reminders"],
)
def get_reminder(reminder_id: UUID, _auth: ECGRead, container: Container) -> ReminderResponse:
    return _reminder(container.ecg_queries().reminder(reminder_id))


@router.post(
    "/repeat-ecg-reminders/{reminder_id}/acknowledge",
    response_model=ReminderResponse,
    tags=["ecg-reminders"],
)
def acknowledge_reminder(
    reminder_id: UUID, body: ReminderTransitionBody, headers: ECGWrite, container: Container
) -> ReminderResponse:
    return _reminder(
        container.ecg_application().acknowledge_reminder(
            reminder_id, headers.actor, headers.idempotency_key, body.expected_version
        )
    )


@router.post(
    "/repeat-ecg-reminders/{reminder_id}/complete",
    response_model=ReminderResponse,
    tags=["ecg-reminders"],
)
def complete_reminder(
    reminder_id: UUID, body: ReminderTransitionBody, headers: ECGWrite, container: Container
) -> ReminderResponse:
    if body.completed_study_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "completed_study_id is required")
    return _reminder(
        container.ecg_application().complete_reminder(
            reminder_id,
            body.completed_study_id,
            headers.actor,
            headers.idempotency_key,
            body.expected_version,
        )
    )


@router.post(
    "/repeat-ecg-reminders/{reminder_id}/cancel",
    response_model=ReminderResponse,
    tags=["ecg-reminders"],
)
def cancel_reminder(
    reminder_id: UUID,
    body: ReminderTransitionBody,
    headers: ECGWrite,
    container: Container,
) -> ReminderResponse:
    if body.cancellation_reason is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cancellation_reason is required")
    return _reminder(
        container.ecg_application().cancel_reminder(
            reminder_id,
            body.cancellation_reason,
            headers.actor,
            headers.idempotency_key,
            body.expected_version,
        )
    )


@router.get(
    "/clinical-cases/{case_id}/ecg-workspace",
    response_model=ECGWorkspaceResponse,
    tags=["ecg-workspace"],
)
def get_workspace(case_id: UUID, _auth: ECGRead, container: Container) -> ECGWorkspaceResponse:
    value = container.ecg_queries().workspace(case_id)
    return ECGWorkspaceResponse(
        clinical_case_id=case_id,
        studies=[_study(item) for item in value.studies],
        current_study=_study(value.current_study) if value.current_study else None,
        quality=_quality(value.quality) if value.quality else None,
        analyses=[_analysis(item) for item in value.analyses],
        interpretations=[_interpretation(item) for item in value.interpretations],
        ingestion_jobs=[_job(item) for item in value.ingestion_jobs],
        comparisons=[_comparison(item) for item in value.comparisons],
        comparison_reviews=[_comparison_review(item) for item in value.comparison_reviews],
        reminders=[_reminder(item) for item in value.reminders],
        capabilities={
            "local_dicom": True,
            "mock_dicom_connector": True,
            "canonical_xml": True,
            "pdf_document": True,
            "dynamic_ecg": len(value.studies) >= 2,
            "repeat_ecg": bool(value.studies),
        },
        data_freshness=utc_now(),
        safety_notice=value.safety_notice,
    )


@router.get("/model-registry/ecg", tags=["model-registry"])
def get_model_info(_auth: ECGRead, container: Container) -> list[dict[str, object]]:
    return [
        {
            "name": value.name,
            "version": value.version,
            "provider_name": value.provider_name,
            "input_contract": value.input_contract,
            "synthetic": value.synthetic,
            "checkpoint_checksum": value.checkpoint_checksum,
            "label_order": list(value.label_order),
            "threshold_source": value.threshold_source,
        }
        for value in container.ecg_queries().model_info()
    ]


@router.get("/model-registry/ecg/health", tags=["model-registry"])
def get_model_health(_auth: ECGRead, container: Container) -> list[dict[str, object]]:
    return [
        {"healthy": value.healthy, "provider_name": value.provider_name, "detail": value.detail}
        for value in container.ecg_queries().provider_health()
    ]


def _study(value: ECGStudySnapshot) -> ECGStudyResponse:
    data = {
        field: getattr(value, field)
        for field in ECGStudyResponse.model_fields
        if field != "source_type"
    }
    return ECGStudyResponse(source_type=value.source_type.value, **data)


def _quality(value: Any) -> QualityResponse:
    return QualityResponse(
        status=value.status.value,
        reason_codes=list(value.reason_codes),
        affected_leads=list(value.affected_leads),
        parser_warnings=list(value.parser_warnings),
        preprocessing_warnings=list(value.preprocessing_warnings),
        quality_engine_version=value.engine_version,
        assessed_at=value.assessed_at,
        suppress_score_emphasis=value.suppress_score_emphasis,
    )


def _job(value: Any) -> IngestionJobResponse:
    return IngestionJobResponse(
        ingestion_job_id=value.id,
        clinical_case_id=value.clinical_case_id,
        source_type=value.source_type.value,
        source_connector_id=value.source_connector_id,
        external_reference=value.external_reference,
        status=value.status.value,
        requested_by_actor_role=value.requested_by_role,
        requested_at=value.requested_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        request_source=value.request_source,
        study_reference=value.study_reference,
        acquisition_at=value.acquisition_at,
        content_type=value.content_type,
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


def _analysis(value: ECGAnalysisSnapshot) -> AnalysisResponse:
    return AnalysisResponse(
        analysis_id=value.analysis_id,
        ecg_study_id=value.ecg_study_id,
        provider_name=value.provider_name,
        provider_version=value.provider_version,
        model_name=value.model_name,
        model_version=value.model_version,
        model_checksum=value.model_checksum,
        preprocessing_version=value.preprocessing_version,
        threshold_version=value.threshold_version,
        status=value.status,
        quality_status=value.quality_status,
        requested_at=value.requested_at,
        completed_at=value.completed_at,
        inference_duration_ms=value.inference_duration_ms,
        findings=[_finding(item) for item in value.findings],
        warnings=list(value.warnings),
        explanation_status=value.explanation_status,
        explanation_artifact_id=value.explanation_artifact_id,
        failure_category=value.failure_category,
        failure_detail_safe=value.failure_detail_safe,
        correlation_id=value.correlation_id,
        record_version=value.record_version,
        synthetic=value.synthetic,
    )


def _finding(value: ECGFindingSnapshot) -> FindingResponse:
    return FindingResponse.model_validate(value, from_attributes=True)


def _interpretation(value: PhysicianInterpretationSnapshot) -> InterpretationResponse:
    return InterpretationResponse.model_validate(value, from_attributes=True)


def _interpretation_command(
    study_id: UUID,
    body: InterpretationBody,
    headers: CommandHeaders,
    supersedes: UUID | None = None,
    reason: str | None = None,
) -> RecordInterpretation:
    return RecordInterpretation(
        headers.actor,
        headers.idempotency_key,
        study_id,
        body.analysis_id,
        body.interpretation_status,
        body.structured_interpretation,
        body.agreement_status,
        body.disagreement_reason,
        body.quality_disposition,
        body.repeat_ecg_requested,
        body.note,
        body.occurred_at,
        body.expected_version,
        supersedes,
        reason,
    )


def _comparison(value: Any) -> ComparisonResponse:
    return ComparisonResponse(
        comparison_id=value.id,
        clinical_case_id=value.clinical_case_id,
        baseline_study_id=value.baseline_study_id,
        current_study_id=value.current_study_id,
        comparison_policy_version=value.comparison_policy_version,
        preprocessing_version=value.preprocessing_version,
        status=value.status.value,
        comparability_status=value.comparability_status.value,
        comparability_reasons=list(value.comparability_reasons),
        lead_comparisons=[
            LeadComparisonResponse.model_validate(item, from_attributes=True)
            for item in value.lead_comparisons
        ],
        technical_change_indicators=list(value.technical_change_indicators),
        signal_feature_deltas=[
            SignalFeatureDeltaResponse.model_validate(item, from_attributes=True)
            for item in value.signal_feature_deltas
        ],
        rhythm_change_indicators=list(value.rhythm_change_indicators),
        st_t_change_indicators=list(value.st_t_change_indicators),
        model_score_deltas=[
            ModelScoreEvolutionResponse.model_validate(item, from_attributes=True)
            for item in value.model_score_deltas
        ],
        model_score_compatibility=value.model_score_compatibility,
        quality_context=value.quality_context,
        review_recommendation=value.review_recommendation,
        requested_by_actor_role=value.requested_by_role,
        requested_at=value.requested_at,
        started_at=value.started_at,
        completed_at=value.completed_at,
        physician_review_status=value.physician_review_status,
        correlation_id=value.correlation_id,
        record_version=value.record_version,
    )


def _reminder(value: Any) -> ReminderResponse:
    return ReminderResponse(
        reminder_id=value.id,
        clinical_case_id=value.clinical_case_id,
        source_study_id=value.source_study_id,
        requested_by=value.requested_by,
        requested_by_actor_role=value.requested_by_role,
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


def _comparison_review(value: Any) -> ComparisonReviewResponse:
    return ComparisonReviewResponse.model_validate(value, from_attributes=True)
