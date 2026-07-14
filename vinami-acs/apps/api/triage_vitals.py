"""Versioned FastAPI contracts for the R2 documentation vertical slice."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field

from apps.api.http import (
    AuthorizedIdentity,
    CommandHeaders,
    ProblemDetail,
    authorize_for,
    command_headers_for,
)
from vinami.identity.domain.security import Permission
from vinami.shared.container import AppContainer
from vinami.triage.application.use_cases import (
    ClinicalDocumentationQueryHandler,
    CorrectTriageAssessment,
    CorrectTriageAssessmentHandler,
    CorrectVitalObservationSet,
    CorrectVitalObservationSetHandler,
    RecordTriageAssessment,
    RecordTriageAssessmentHandler,
    RecordVitalObservationSet,
    RecordVitalObservationSetHandler,
    TriageContent,
    TriageVitalsSummaryDTO,
    UnitOfWorkFactory,
    VitalContent,
)
from vinami.triage.domain.model import (
    DataQualityStatus,
    ObservationState,
    OnsetPrecision,
    StructuredObservation,
    TriageAssessment,
    VitalKind,
    VitalMeasurement,
    VitalObservationSet,
)

router = APIRouter(prefix="/api/v1/clinical-cases")

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ProblemDetail, "description": "Domain invariant rejected the command"},
    401: {"model": ProblemDetail, "description": "Missing or invalid verified identity"},
    403: {"model": ProblemDetail, "description": "Verified identity lacks permission"},
    404: {"model": ProblemDetail, "description": "Case or documentation record not found"},
    409: {"model": ProblemDetail, "description": "Version, idempotency, or case-state conflict"},
    422: {
        "model": ProblemDetail,
        "description": "Request schema validation failed",
    },
}


class StructuredObservationModel(BaseModel):
    """One explicitly present, absent, unknown, or unassessed fact."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=240)
    state: ObservationState
    note: str | None = Field(default=None, min_length=1, max_length=2000)


class TriageContentModel(BaseModel):
    """Non-diagnostic triage documentation fields."""

    model_config = ConfigDict(extra="forbid")
    chief_complaint: str | None = Field(default=None, min_length=1, max_length=4000)
    symptom_onset_state: ObservationState = ObservationState.NOT_ASSESSED
    symptom_onset_at: datetime | None = None
    symptom_onset_precision: OnsetPrecision | None = None
    symptom_description: str | None = Field(default=None, min_length=1, max_length=4000)
    symptom_location: str | None = Field(default=None, min_length=1, max_length=2000)
    symptom_radiation: str | None = Field(default=None, min_length=1, max_length=2000)
    symptom_duration: str | None = Field(default=None, min_length=1, max_length=500)
    symptom_pattern: str | None = Field(default=None, min_length=1, max_length=1000)
    aggravating_factors: str | None = Field(default=None, min_length=1, max_length=4000)
    relieving_factors: str | None = Field(default=None, min_length=1, max_length=4000)
    relevant_history_summary: str | None = Field(default=None, min_length=1, max_length=8000)
    current_medication_summary: str | None = Field(default=None, min_length=1, max_length=8000)
    allergy_summary: str | None = Field(default=None, min_length=1, max_length=8000)
    clinical_note: str | None = Field(default=None, min_length=1, max_length=12000)
    associated_symptoms: list[StructuredObservationModel] = Field(default_factory=list)
    cardiovascular_risk_factors: list[StructuredObservationModel] = Field(default_factory=list)


class RecordTriageAssessmentRequest(TriageContentModel):
    """Record the first triage revision for a case."""

    expected_case_version: int = Field(ge=1)
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=160)


class CorrectTriageAssessmentRequest(TriageContentModel):
    """Append a corrected triage revision with a mandatory reason."""

    expected_record_version: int = Field(ge=1)
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=160)
    correction_reason: str = Field(min_length=1, max_length=2000)


class VitalMeasurementRequest(BaseModel):
    """One explicit-unit raw observation."""

    model_config = ConfigDict(extra="forbid")
    kind: VitalKind
    value: float
    unit: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=160)
    observed_at: datetime
    quality_status: DataQualityStatus = DataQualityStatus.UNKNOWN


class VitalContentModel(BaseModel):
    """One set of observations captured together."""

    model_config = ConfigDict(extra="forbid")
    measurements: list[VitalMeasurementRequest] = Field(min_length=1, max_length=7)
    device_reference: str | None = Field(default=None, min_length=1, max_length=500)
    supplemental_oxygen_state: ObservationState = ObservationState.NOT_ASSESSED
    oxygen_delivery_method: str | None = Field(default=None, min_length=1, max_length=500)
    level_of_consciousness: str | None = Field(default=None, min_length=1, max_length=1000)
    observation_note: str | None = Field(default=None, min_length=1, max_length=4000)


class RecordVitalObservationSetRequest(VitalContentModel):
    """Record a new chronological vital set."""

    expected_case_version: int = Field(ge=1)
    observed_at: datetime
    source: str = Field(min_length=1, max_length=160)


class CorrectVitalObservationSetRequest(VitalContentModel):
    """Append a corrected vital-set revision."""

    expected_record_version: int = Field(ge=1)
    observed_at: datetime
    source: str = Field(min_length=1, max_length=160)
    correction_reason: str = Field(min_length=1, max_length=2000)


class StructuredObservationResponse(StructuredObservationModel):
    """Rendered structured state."""


class TriageAssessmentResponse(TriageContentModel):
    """One persisted triage revision with complete provenance."""

    assessment_id: UUID
    clinical_case_id: UUID
    revision_number: int
    status: str
    source: str
    recorded_by_actor_id: UUID
    recorded_by_actor_role: str
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    record_version: int
    corrects_assessment_id: UUID | None
    correction_reason: str | None


class TriageHistoryResponse(BaseModel):
    """Reverse-chronological immutable triage revisions."""

    items: list[TriageAssessmentResponse]
    total: int


class VitalMeasurementResponse(BaseModel):
    """One persisted raw measurement."""

    kind: str
    value: float
    unit: str
    source: str
    observed_at: datetime
    quality_status: str


class VitalObservationSetResponse(BaseModel):
    """One persisted vital-set revision with provenance."""

    vital_set_id: UUID
    clinical_case_id: UUID
    encounter_id: UUID
    sequence_number: int
    revision_number: int
    source: str
    device_reference: str | None
    recorded_by_actor_id: UUID
    recorded_by_actor_role: str
    observed_at: datetime
    recorded_at: datetime
    correlation_id: UUID
    causation_id: UUID | None
    record_version: int
    measurements: list[VitalMeasurementResponse]
    supplemental_oxygen_state: str
    oxygen_delivery_method: str | None
    level_of_consciousness: str | None
    observation_note: str | None
    corrects_vital_set_id: UUID | None
    correction_reason: str | None


class VitalObservationHistoryResponse(BaseModel):
    """Reverse-chronological vital-set revisions."""

    items: list[VitalObservationSetResponse]
    total: int


class MissingDocumentationItemResponse(BaseModel):
    identifier: str
    description: str


class TriageVitalsSummaryResponse(BaseModel):
    """Current documentation and neutral completeness output."""

    current_triage: TriageAssessmentResponse | None
    latest_vitals: VitalObservationSetResponse | None
    recent_vitals: list[VitalObservationSetResponse]
    missing_documentation: list[MissingDocumentationItemResponse]
    completeness_policy_version: str
    data_freshness_at: datetime
    case_version: int


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _uow(container: AppContainer) -> UnitOfWorkFactory:
    return cast(UnitOfWorkFactory, container.unit_of_work)


ContainerDependency = Annotated[AppContainer, Depends(_container)]
TriageWrite = Annotated[CommandHeaders, Depends(command_headers_for(Permission.TRIAGE_WRITE))]
VitalsWrite = Annotated[CommandHeaders, Depends(command_headers_for(Permission.VITALS_WRITE))]
TriageRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TRIAGE_READ))]
VitalsRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.VITALS_READ))]


@router.post(
    "/{case_id}/triage-assessments",
    response_model=TriageAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["triage"],
    summary="Record structured triage documentation",
    responses=ERROR_RESPONSES,
)
def record_triage(
    case_id: UUID,
    body: RecordTriageAssessmentRequest,
    headers: TriageWrite,
    container: ContainerDependency,
) -> TriageAssessmentResponse:
    result = RecordTriageAssessmentHandler(_uow(container)).execute(
        RecordTriageAssessment(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            clinical_case_id=case_id,
            expected_case_version=body.expected_case_version,
            occurred_at=body.occurred_at,
            source=body.source,
            content=_triage_content(body),
        )
    )
    return _triage_response(result.assessment)


@router.get(
    "/{case_id}/triage",
    response_model=TriageAssessmentResponse | None,
    tags=["triage"],
    summary="Get current triage documentation",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404]},
)
def get_current_triage(
    case_id: UUID, _authorization: TriageRead, container: ContainerDependency
) -> TriageAssessmentResponse | None:
    value = ClinicalDocumentationQueryHandler(_uow(container)).current_triage(case_id)
    return _triage_response(value) if value is not None else None


@router.get(
    "/{case_id}/triage/history",
    response_model=TriageHistoryResponse,
    tags=["triage"],
    summary="List immutable triage revisions",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404]},
)
def get_triage_history(
    case_id: UUID, _authorization: TriageRead, container: ContainerDependency
) -> TriageHistoryResponse:
    values = ClinicalDocumentationQueryHandler(_uow(container)).triage_history(case_id)
    return TriageHistoryResponse(
        items=[_triage_response(value) for value in values], total=len(values)
    )


@router.post(
    "/{case_id}/triage-assessments/{assessment_id}/corrections",
    response_model=TriageAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["triage"],
    summary="Correct triage documentation without overwriting history",
    responses=ERROR_RESPONSES,
)
def correct_triage(
    case_id: UUID,
    assessment_id: UUID,
    body: CorrectTriageAssessmentRequest,
    headers: TriageWrite,
    container: ContainerDependency,
) -> TriageAssessmentResponse:
    result = CorrectTriageAssessmentHandler(_uow(container)).execute(
        CorrectTriageAssessment(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            clinical_case_id=case_id,
            assessment_id=assessment_id,
            expected_record_version=body.expected_record_version,
            occurred_at=body.occurred_at,
            source=body.source,
            correction_reason=body.correction_reason,
            content=_triage_content(body),
        )
    )
    return _triage_response(result.assessment)


@router.post(
    "/{case_id}/vital-observation-sets",
    response_model=VitalObservationSetResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["vitals"],
    summary="Record a vital observation set",
    responses=ERROR_RESPONSES,
)
def record_vitals(
    case_id: UUID,
    body: RecordVitalObservationSetRequest,
    headers: VitalsWrite,
    container: ContainerDependency,
) -> VitalObservationSetResponse:
    result = RecordVitalObservationSetHandler(_uow(container)).execute(
        RecordVitalObservationSet(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            clinical_case_id=case_id,
            expected_case_version=body.expected_case_version,
            observed_at=body.observed_at,
            source=body.source,
            content=_vital_content(body),
        )
    )
    return _vital_response(result.vital_set)


@router.get(
    "/{case_id}/vitals",
    response_model=VitalObservationHistoryResponse,
    tags=["vitals"],
    summary="List repeated vital observations and corrections",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404]},
)
def get_vital_history(
    case_id: UUID, _authorization: VitalsRead, container: ContainerDependency
) -> VitalObservationHistoryResponse:
    values = ClinicalDocumentationQueryHandler(_uow(container)).vital_history(case_id)
    return VitalObservationHistoryResponse(
        items=[_vital_response(value) for value in values], total=len(values)
    )


@router.get(
    "/{case_id}/vitals/latest",
    response_model=VitalObservationSetResponse | None,
    tags=["vitals"],
    summary="Get the latest vital observation set",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404]},
)
def get_latest_vitals(
    case_id: UUID, _authorization: VitalsRead, container: ContainerDependency
) -> VitalObservationSetResponse | None:
    value = ClinicalDocumentationQueryHandler(_uow(container)).latest_vitals(case_id)
    return _vital_response(value) if value is not None else None


@router.post(
    "/{case_id}/vital-observation-sets/{vital_set_id}/corrections",
    response_model=VitalObservationSetResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["vitals"],
    summary="Correct a vital set without overwriting history",
    responses=ERROR_RESPONSES,
)
def correct_vitals(
    case_id: UUID,
    vital_set_id: UUID,
    body: CorrectVitalObservationSetRequest,
    headers: VitalsWrite,
    container: ContainerDependency,
) -> VitalObservationSetResponse:
    result = CorrectVitalObservationSetHandler(_uow(container)).execute(
        CorrectVitalObservationSet(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            clinical_case_id=case_id,
            vital_set_id=vital_set_id,
            expected_record_version=body.expected_record_version,
            observed_at=body.observed_at,
            source=body.source,
            correction_reason=body.correction_reason,
            content=_vital_content(body),
        )
    )
    return _vital_response(result.vital_set)


@router.get(
    "/{case_id}/triage-vitals-summary",
    response_model=TriageVitalsSummaryResponse,
    tags=["triage", "vitals"],
    summary="Get current documentation and backend completeness results",
    responses={401: ERROR_RESPONSES[401], 403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404]},
)
def get_triage_vitals_summary(
    case_id: UUID, _authorization: TriageRead, container: ContainerDependency
) -> TriageVitalsSummaryResponse:
    return _summary_response(ClinicalDocumentationQueryHandler(_uow(container)).summary(case_id))


def _triage_content(value: TriageContentModel) -> TriageContent:
    return TriageContent(
        chief_complaint=value.chief_complaint,
        symptom_onset_state=value.symptom_onset_state,
        symptom_onset_at=value.symptom_onset_at,
        symptom_onset_precision=value.symptom_onset_precision,
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
        associated_symptoms=tuple(_structured(item) for item in value.associated_symptoms),
        cardiovascular_risk_factors=tuple(
            _structured(item) for item in value.cardiovascular_risk_factors
        ),
    )


def _vital_content(value: VitalContentModel) -> VitalContent:
    return VitalContent(
        measurements=tuple(
            VitalMeasurement(
                kind=item.kind,
                value=item.value,
                unit=item.unit,
                source=item.source,
                observed_at=item.observed_at,
                quality_status=item.quality_status,
            )
            for item in value.measurements
        ),
        device_reference=value.device_reference,
        supplemental_oxygen_state=value.supplemental_oxygen_state,
        oxygen_delivery_method=value.oxygen_delivery_method,
        level_of_consciousness=value.level_of_consciousness,
        observation_note=value.observation_note,
    )


def _structured(value: StructuredObservationModel) -> StructuredObservation:
    return StructuredObservation(name=value.name, state=value.state, note=value.note)


def _triage_response(value: TriageAssessment) -> TriageAssessmentResponse:
    return TriageAssessmentResponse(
        assessment_id=value.id,
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
        symptom_onset_state=value.symptom_onset_state,
        symptom_onset_at=value.symptom_onset_at,
        symptom_onset_precision=value.symptom_onset_precision,
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
        associated_symptoms=[_structured_response(item) for item in value.associated_symptoms],
        cardiovascular_risk_factors=[
            _structured_response(item) for item in value.cardiovascular_risk_factors
        ],
        corrects_assessment_id=value.corrects_assessment_id,
        correction_reason=value.correction_reason,
    )


def _structured_response(value: StructuredObservation) -> StructuredObservationModel:
    return StructuredObservationModel(name=value.name, state=value.state, note=value.note)


def _vital_response(value: VitalObservationSet) -> VitalObservationSetResponse:
    return VitalObservationSetResponse(
        vital_set_id=value.id,
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
        measurements=[
            VitalMeasurementResponse(
                kind=item.kind.value,
                value=item.value,
                unit=item.unit,
                source=item.source,
                observed_at=item.observed_at,
                quality_status=item.quality_status.value,
            )
            for item in value.measurements
        ],
        supplemental_oxygen_state=value.supplemental_oxygen_state.value,
        oxygen_delivery_method=value.oxygen_delivery_method,
        level_of_consciousness=value.level_of_consciousness,
        observation_note=value.observation_note,
        corrects_vital_set_id=value.corrects_vital_set_id,
        correction_reason=value.correction_reason,
    )


def _summary_response(value: TriageVitalsSummaryDTO) -> TriageVitalsSummaryResponse:
    return TriageVitalsSummaryResponse(
        current_triage=_triage_response(value.current_triage) if value.current_triage else None,
        latest_vitals=_vital_response(value.latest_vitals) if value.latest_vitals else None,
        recent_vitals=[_vital_response(item) for item in value.recent_vitals],
        missing_documentation=[
            MissingDocumentationItemResponse(
                identifier=item.identifier, description=item.description
            )
            for item in value.missing_documentation
        ],
        completeness_policy_version=value.completeness_policy_version,
        data_freshness_at=value.data_freshness_at,
        case_version=value.case_version,
    )
