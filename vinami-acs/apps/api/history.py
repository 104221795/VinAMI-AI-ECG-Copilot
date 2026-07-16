"""R9 API routes for Timeline, Audit, Outcome, provenance and research export."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from apps.api.http import (
    AuthorizedIdentity,
    CommandHeaders,
    ProblemDetail,
    authorize_for,
    command_headers_for,
)
from vinami.audit.application.history import (
    CaseHistoryApplicationService,
    CaseHistoryQueryService,
    CorrectOutcomeCommand,
    RecordOutcomeCommand,
    RequestResearchExportCommand,
)
from vinami.audit.domain.model import Outcome
from vinami.audit.ports.history import ModelProvenance, ResearchExport
from vinami.identity.domain.security import Permission
from vinami.shared.container import AppContainer

router = APIRouter(prefix="/api/v1")

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ProblemDetail, "description": "Malformed command context"},
    401: {"model": ProblemDetail, "description": "Missing or invalid verified identity"},
    403: {"model": ProblemDetail, "description": "Verified identity lacks permission"},
    404: {"model": ProblemDetail, "description": "Resource not found"},
    409: {"model": ProblemDetail, "description": "Lifecycle or idempotency conflict"},
    422: {"model": ProblemDetail, "description": "Request validation failed"},
}


class TimelineHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeline_event_id: UUID
    clinical_case_id: UUID
    event_type: str
    title: str
    occurred_at: datetime
    recorded_at: datetime
    source: str
    actor_id: UUID | None
    correlation_id: UUID
    causation_id: UUID | None
    source_record_id: UUID | None
    source_record_version: int | None
    correction_status: str
    supersedes_timeline_event_id: UUID | None
    revokes_timeline_event_id: UUID | None
    data_classification: str


class TimelineHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TimelineHistoryItem]
    page: int
    page_size: int
    total: int


class AuditHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_id: UUID
    actor_id: UUID | None
    actor_role: str | None
    identity_subject: str | None
    actor_roles: tuple[str, ...]
    applied_permission: str | None
    identity_provider: str | None
    authentication_method: str | None
    session_reference: str | None
    action: str
    resource_type: str
    resource_id: UUID
    request_source: str
    correlation_id: UUID
    causation_id: UUID | None
    prior_version: int | None
    resulting_version: int | None
    outcome: str
    reason: str | None
    recorded_at: datetime
    idempotency_key: str | None
    authorization_result: str | None
    correction_status: str
    source_record_version: int | None


class AuditHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditHistoryItem]
    page: int
    page_size: int
    total: int


class OutcomeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_id: UUID
    clinical_case_id: UUID
    outcome_type: str
    outcome_timestamp: datetime
    final_conclusion: str
    disposition: str | None
    destination: str | None
    cath_lab_review_outcome: str | None
    intervention_reference: str | None
    complications: str | None
    follow_up_status: str | None
    data_completeness: str
    source: str
    uncertainty: str | None
    unavailable_reason: str | None
    recorded_at: datetime
    recorded_by: UUID
    actor_role: str
    revision_number: int
    record_version: int
    supersedes_outcome_id: UUID | None
    correction_reason: str | None
    correlation_id: UUID | None
    causation_id: UUID | None


class OutcomeHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current: OutcomeResponse | None
    revisions: list[OutcomeResponse]
    safety_notice: str


class OutcomeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome_type: str = Field(min_length=1, max_length=80)
    outcome_timestamp: datetime
    final_conclusion: str = Field(min_length=1, max_length=4000)
    disposition: str | None = Field(default=None, max_length=240)
    destination: str | None = Field(default=None, max_length=240)
    cath_lab_review_outcome: str | None = Field(default=None, max_length=4000)
    intervention_reference: str | None = Field(default=None, max_length=4000)
    complications: str | None = Field(default=None, max_length=4000)
    follow_up_status: str | None = Field(default=None, max_length=4000)
    data_completeness: str = Field(default="documented", min_length=1, max_length=80)
    source: str = Field(default="physician_documented", min_length=1, max_length=120)
    uncertainty: str | None = Field(default=None, max_length=4000)
    unavailable_reason: str | None = Field(default=None, max_length=4000)


class OutcomeCorrectionBody(OutcomeBody):
    correction_reason: str = Field(min_length=1, max_length=4000)


class ModelProvenanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    study_id: UUID
    provider_name: str
    provider_version: str
    model_name: str
    model_version: str
    model_checksum: str | None
    threshold_version: str | None
    preprocessing_version: str
    label_mapping_version: str
    executed_at: datetime | None
    input_quality: str
    input_artifact_id: UUID
    input_artifact_checksum: str
    explanation_artifact_id: UUID | None
    explanation_status: str
    synthetic: bool
    status: str
    warnings: tuple[str, ...]
    record_version: int
    safety_notice: str


class ResearchExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_ids: list[UUID] = Field(min_length=1, max_length=100)


class ResearchExportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: UUID
    status: str
    schema_version: str
    requested_by: UUID
    requested_by_role: str
    requested_at: datetime
    completed_at: datetime | None
    case_ids: tuple[UUID, ...]
    filters: dict[str, object]
    row_count: int
    pseudonymization_method: str
    checksum_sha256: str
    content_json: dict[str, object]
    content_csv: str
    correlation_id: UUID
    metadata: dict[str, object]
    safety_notice: str


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _timeline_item(item: dict[str, object]) -> TimelineHistoryItem:
    return TimelineHistoryItem(
        timeline_event_id=cast(UUID, item["timeline_event_id"]),
        clinical_case_id=cast(UUID, item["clinical_case_id"]),
        event_type=cast(str, item["event_type"]),
        title=cast(str, item["title"]),
        occurred_at=cast(datetime, item["occurred_at"]),
        recorded_at=cast(datetime, item["recorded_at"]),
        source=cast(str, item["source"]),
        actor_id=cast(UUID | None, item["actor_id"]),
        correlation_id=cast(UUID, item["correlation_id"]),
        causation_id=cast(UUID | None, item["causation_id"]),
        source_record_id=cast(UUID | None, item["source_record_id"]),
        source_record_version=cast(int | None, item["source_record_version"]),
        correction_status=cast(str, item["correction_status"]),
        supersedes_timeline_event_id=cast(UUID | None, item["supersedes_timeline_event_id"]),
        revokes_timeline_event_id=cast(UUID | None, item["revokes_timeline_event_id"]),
        data_classification=cast(str, item["data_classification"]),
    )


def _audit_item(item: dict[str, object]) -> AuditHistoryItem:
    return AuditHistoryItem(
        audit_id=cast(UUID, item["audit_id"]),
        actor_id=cast(UUID | None, item["actor_id"]),
        actor_role=cast(str | None, item["actor_role"]),
        identity_subject=cast(str | None, item["identity_subject"]),
        actor_roles=cast(tuple[str, ...], item["actor_roles"]),
        applied_permission=cast(str | None, item["applied_permission"]),
        identity_provider=cast(str | None, item["identity_provider"]),
        authentication_method=cast(str | None, item["authentication_method"]),
        session_reference=cast(str | None, item["session_reference"]),
        action=cast(str, item["action"]),
        resource_type=cast(str, item["resource_type"]),
        resource_id=cast(UUID, item["resource_id"]),
        request_source=cast(str, item["request_source"]),
        correlation_id=cast(UUID, item["correlation_id"]),
        causation_id=cast(UUID | None, item["causation_id"]),
        prior_version=cast(int | None, item["prior_version"]),
        resulting_version=cast(int | None, item["resulting_version"]),
        outcome=cast(str, item["outcome"]),
        reason=cast(str | None, item["reason"]),
        recorded_at=cast(datetime, item["recorded_at"]),
        idempotency_key=cast(str | None, item["idempotency_key"]),
        authorization_result=cast(str | None, item["authorization_result"]),
        correction_status=cast(str, item["correction_status"]),
        source_record_version=cast(int | None, item["source_record_version"]),
    )


ContainerDependency = Annotated[AppContainer, Depends(_container)]
TimelineRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TIMELINE_READ))]
AuditRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.AUDIT_READ))]
CaseRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.CLINICAL_CASE_READ))]
OutcomeWrite = Annotated[CommandHeaders, Depends(command_headers_for(Permission.OUTCOME_WRITE))]
ResearchExportCreate = Annotated[
    CommandHeaders, Depends(command_headers_for(Permission.RESEARCH_EXPORT_CREATE))
]


@router.get(
    "/clinical-cases/{case_id}/history/timeline",
    response_model=TimelineHistoryPage,
    tags=["timeline"],
    summary="Get consolidated immutable case Timeline",
    responses=ERROR_RESPONSES,
)
def get_timeline_history(
    case_id: UUID,
    authorization: TimelineRead,
    container: ContainerDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    event_type: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    correction_status: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
) -> TimelineHistoryPage:
    result = _queries(container).timeline(
        case_id,
        tuple(authorization.identity.location_scope),
        page,
        page_size,
        event_type,
        correction_status,
    )
    return TimelineHistoryPage(
        items=[_timeline_item(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )


@router.get(
    "/clinical-cases/{case_id}/history/audit",
    response_model=AuditHistoryPage,
    tags=["audit"],
    summary="Get detailed immutable case Audit",
    responses=ERROR_RESPONSES,
)
def get_audit_history(
    case_id: UUID,
    authorization: AuditRead,
    container: ContainerDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    action: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    outcome: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
) -> AuditHistoryPage:
    result = _queries(container).audit(
        case_id,
        tuple(authorization.identity.location_scope),
        page,
        page_size,
        action,
        outcome,
    )
    return AuditHistoryPage(
        items=[_audit_item(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )


@router.get(
    "/clinical-cases/{case_id}/outcomes",
    response_model=OutcomeHistoryResponse,
    tags=["outcomes"],
    summary="Get current outcome and immutable revisions",
    responses=ERROR_RESPONSES,
)
def get_outcomes(
    case_id: UUID, authorization: CaseRead, container: ContainerDependency
) -> OutcomeHistoryResponse:
    revisions = _queries(container).outcomes(case_id, tuple(authorization.identity.location_scope))
    responses = [_outcome(item) for item in revisions]
    return OutcomeHistoryResponse(
        current=responses[0] if responses else None,
        revisions=responses,
        safety_notice=(
            "Outcome records are physician-authored or explicitly sourced. "
            "They are not inferred from AI, tasks or workflow completion."
        ),
    )


@router.post(
    "/clinical-cases/{case_id}/outcomes",
    response_model=OutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["outcomes"],
    summary="Record the initial Clinical Outcome",
    responses=ERROR_RESPONSES,
)
def record_outcome(
    case_id: UUID,
    body: OutcomeBody,
    headers: OutcomeWrite,
    container: ContainerDependency,
) -> OutcomeResponse:
    outcome = _application(container).record_outcome(
        RecordOutcomeCommand(
            command_id=uuid4(),
            case_id=case_id,
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            **body.model_dump(),
        ),
        _visible_locations(headers),
    )
    return _outcome(outcome)


@router.post(
    "/clinical-cases/{case_id}/outcomes/{outcome_id}/corrections",
    response_model=OutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["outcomes"],
    summary="Append a Clinical Outcome correction",
    responses=ERROR_RESPONSES,
)
def correct_outcome(
    case_id: UUID,
    outcome_id: UUID,
    body: OutcomeCorrectionBody,
    headers: OutcomeWrite,
    container: ContainerDependency,
) -> OutcomeResponse:
    outcome = _application(container).correct_outcome(
        CorrectOutcomeCommand(
            command_id=uuid4(),
            case_id=case_id,
            outcome_id=outcome_id,
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            **body.model_dump(),
        ),
        _visible_locations(headers),
    )
    return _outcome(outcome)


@router.get(
    "/clinical-cases/{case_id}/model-provenance",
    response_model=list[ModelProvenanceResponse],
    tags=["model-registry"],
    summary="Get persisted model and evidence provenance for a case",
    responses=ERROR_RESPONSES,
)
def get_model_provenance(
    case_id: UUID, authorization: CaseRead, container: ContainerDependency
) -> list[ModelProvenanceResponse]:
    values = _queries(container).model_provenance(
        case_id, tuple(authorization.identity.location_scope)
    )
    return [_provenance(item) for item in values]


@router.post(
    "/research-exports",
    response_model=ResearchExportResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["learning-data"],
    summary="Generate an authorized research-use case export",
    responses=ERROR_RESPONSES,
)
def request_research_export(
    body: ResearchExportBody,
    headers: ResearchExportCreate,
    container: ContainerDependency,
) -> ResearchExportResponse:
    export = _application(container).request_research_export(
        RequestResearchExportCommand(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            case_ids=tuple(body.case_ids),
            visible_locations=_visible_locations(headers),
        )
    )
    return _export(export)


@router.get(
    "/research-exports/{export_id}",
    response_model=ResearchExportResponse,
    tags=["learning-data"],
    summary="Get research-use export metadata and generated payload",
    responses=ERROR_RESPONSES,
)
def get_research_export(
    export_id: UUID, _authorization: CaseRead, container: ContainerDependency
) -> ResearchExportResponse:
    return _export(_queries(container).research_export(export_id))


def _queries(container: AppContainer) -> CaseHistoryQueryService:
    return container.case_history_queries()


def _application(container: AppContainer) -> CaseHistoryApplicationService:
    return container.case_history_application()


def _visible_locations(headers: CommandHeaders) -> tuple[str, ...]:
    return headers.visible_locations


def _outcome(value: Outcome) -> OutcomeResponse:
    return OutcomeResponse(
        outcome_id=value.id,
        clinical_case_id=value.case_id,
        outcome_type=value.outcome_type,
        outcome_timestamp=value.outcome_timestamp,
        final_conclusion=value.final_conclusion,
        disposition=value.disposition,
        destination=value.destination,
        cath_lab_review_outcome=value.cath_lab_review_outcome,
        intervention_reference=value.intervention_reference,
        complications=value.complications,
        follow_up_status=value.follow_up_status,
        data_completeness=value.data_completeness,
        source=value.source,
        uncertainty=value.uncertainty,
        unavailable_reason=value.unavailable_reason,
        recorded_at=value.recorded_at,
        recorded_by=value.recorded_by,
        actor_role=value.actor_role,
        revision_number=value.revision_number,
        record_version=value.record_version,
        supersedes_outcome_id=value.supersedes_outcome_id,
        correction_reason=value.correction_reason,
        correlation_id=value.correlation_id,
        causation_id=value.causation_id,
    )


def _provenance(value: ModelProvenance) -> ModelProvenanceResponse:
    return ModelProvenanceResponse(
        analysis_id=value.analysis_id,
        study_id=value.study_id,
        provider_name=value.provider_name,
        provider_version=value.provider_version,
        model_name=value.model_name,
        model_version=value.model_version,
        model_checksum=value.model_checksum,
        threshold_version=value.threshold_version,
        preprocessing_version=value.preprocessing_version,
        label_mapping_version=value.label_mapping_version,
        executed_at=value.executed_at,
        input_quality=value.input_quality,
        input_artifact_id=value.input_artifact_id,
        input_artifact_checksum=value.input_artifact_checksum,
        explanation_artifact_id=value.explanation_artifact_id,
        explanation_status=value.explanation_status,
        synthetic=value.synthetic,
        status=value.status,
        warnings=value.warnings,
        record_version=value.record_version,
        safety_notice=(
            "Model outputs are research-use scores and attention artifacts, "
            "not diagnoses or validated clinical probabilities."
        ),
    )


def _export(value: ResearchExport) -> ResearchExportResponse:
    return ResearchExportResponse(
        export_id=value.export_id,
        status=value.status,
        schema_version=value.schema_version,
        requested_by=value.requested_by,
        requested_by_role=value.requested_by_role,
        requested_at=value.requested_at,
        completed_at=value.completed_at,
        case_ids=value.case_ids,
        filters=value.filters,
        row_count=value.row_count,
        pseudonymization_method=value.pseudonymization_method,
        checksum_sha256=value.checksum_sha256,
        content_json=value.content_json,
        content_csv=value.content_csv,
        correlation_id=value.correlation_id,
        metadata=value.metadata,
        safety_notice=(
            "Research exports are pseudonymized MVP artifacts and do not imply "
            "clinical validation or automated model learning."
        ),
    )
