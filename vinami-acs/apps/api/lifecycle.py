"""Versioned FastAPI routes for the R1 clinical lifecycle vertical slice."""

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
from vinami.clinical_case.application.lifecycle import (
    ClinicalCaseDTO,
    ClinicalCasePageDTO,
    ClinicalCaseQueryHandler,
    GetClinicalCase,
    ListActiveClinicalCases,
    OpenClinicalCase,
    OpenClinicalCaseHandler,
)
from vinami.clinical_case.application.lifecycle import (
    UnitOfWorkFactory as ClinicalCaseUnitOfWorkFactory,
)
from vinami.clinical_case.domain.model import CaseStatus, ClinicalPriority
from vinami.clinical_case.ports.read_models import AuditReadRecord, TimelineReadRecord
from vinami.identity.domain.security import Permission
from vinami.patient.application.lifecycle import (
    EncounterDTO,
    GetEncounter,
    GetPatient,
    PatientDTO,
    PatientQueryHandler,
    RegisterPatient,
    RegisterPatientHandler,
    SafeDemographicSummary,
    StartEncounter,
    StartEncounterHandler,
)
from vinami.patient.application.lifecycle import (
    UnitOfWorkFactory as PatientUnitOfWorkFactory,
)
from vinami.shared.container import AppContainer
from vinami.shared.domain import utc_now

router = APIRouter(prefix="/api/v1")
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ProblemDetail, "description": "Malformed command context"},
    401: {"model": ProblemDetail, "description": "Missing or invalid verified identity"},
    403: {"model": ProblemDetail, "description": "Verified identity lacks permission"},
    404: {"model": ProblemDetail, "description": "Resource not found"},
    409: {"model": ProblemDetail, "description": "Lifecycle or idempotency conflict"},
    422: {"model": ProblemDetail, "description": "Request validation failed"},
}


class SafeDemographicSummaryModel(BaseModel):
    """Optional non-identifying demographic summary."""

    model_config = ConfigDict(extra="forbid")

    age_band: str | None = Field(default=None, max_length=40, examples=["45-64"])
    sex_at_birth: str | None = Field(default=None, max_length=50, examples=["female"])


class RegisterPatientRequest(BaseModel):
    """Register one synthetic or non-sensitive external Patient reference."""

    model_config = ConfigDict(extra="forbid")

    patient_reference: str = Field(min_length=1, max_length=120, examples=["SYN-R1-001"])
    safe_demographic_summary: SafeDemographicSummaryModel = Field(
        default_factory=SafeDemographicSummaryModel
    )


class PatientResponse(BaseModel):
    """Public Patient lifecycle representation without names or exact birth date."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "patient_id": "8b78f75f-dfce-4ed4-948a-b25e186b645a",
                    "patient_reference": "SYN-R1-001",
                    "reference_system": "vinami.r1.synthetic",
                    "safe_demographic_summary": {
                        "age_band": "45-64",
                        "sex_at_birth": "female",
                    },
                    "created_at": "2026-07-13T08:00:00Z",
                    "updated_at": "2026-07-13T08:00:00Z",
                    "aggregate_version": 1,
                }
            ]
        }
    )

    patient_id: UUID
    patient_reference: str
    reference_system: str
    safe_demographic_summary: SafeDemographicSummaryModel
    created_at: datetime
    updated_at: datetime
    aggregate_version: int


class StartEncounterRequest(BaseModel):
    """Start an Encounter for an existing Patient."""

    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    location: str = Field(min_length=1, max_length=160, examples=["Emergency Department"])
    arrival_at: datetime
    external_reference: str | None = Field(default=None, min_length=1, max_length=120)


class EncounterResponse(BaseModel):
    """Public Encounter lifecycle representation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "encounter_id": "527558b7-6a68-46f9-8b03-b13dbc07ff0b",
                    "patient_id": "8b78f75f-dfce-4ed4-948a-b25e186b645a",
                    "location": "Emergency Department",
                    "status": "active",
                    "arrival_at": "2026-07-13T08:05:00Z",
                    "created_at": "2026-07-13T08:05:00Z",
                    "updated_at": "2026-07-13T08:05:00Z",
                    "aggregate_version": 1,
                }
            ]
        }
    )

    encounter_id: UUID
    patient_id: UUID
    location: str
    status: str
    arrival_at: datetime
    created_at: datetime
    updated_at: datetime
    aggregate_version: int


class OpenClinicalCaseRequest(BaseModel):
    """Open a suspected ACS case for an existing Encounter."""

    model_config = ConfigDict(extra="forbid")

    encounter_id: UUID
    opening_reason: str = Field(
        min_length=1, max_length=1000, examples=["Suspected ACS clinical review"]
    )
    priority: ClinicalPriority


class ClinicalCaseResponse(BaseModel):
    """Public Clinical Case lifecycle representation."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "case_id": "426a2b5f-2456-4d4e-b3be-e7933e7687a6",
                    "encounter_id": "527558b7-6a68-46f9-8b03-b13dbc07ff0b",
                    "opening_reason": "Suspected ACS clinical review",
                    "priority": "urgent",
                    "status": "open",
                    "opened_at": "2026-07-13T08:10:00Z",
                    "updated_at": "2026-07-13T08:10:00Z",
                    "aggregate_version": 1,
                }
            ]
        }
    )

    case_id: UUID
    encounter_id: UUID
    opening_reason: str
    priority: str
    status: str
    opened_at: datetime
    updated_at: datetime
    aggregate_version: int


class ClinicalCaseListItem(BaseModel):
    """One active case queue item."""

    case_id: UUID
    encounter_id: UUID
    priority: str
    status: str
    location: str
    opened_at: datetime
    updated_at: datetime
    aggregate_version: int


class PaginatedClinicalCasesResponse(BaseModel):
    """Deterministic page of active cases."""

    items: list[ClinicalCaseListItem]
    page: int
    page_size: int
    total: int


class TimelineEventResponse(BaseModel):
    """Persisted lifecycle timeline projection."""

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


class AuditEntryResponse(BaseModel):
    """Immutable lifecycle audit projection."""

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


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def _patient_unit_of_work(container: AppContainer) -> PatientUnitOfWorkFactory:
    return cast(PatientUnitOfWorkFactory, container.unit_of_work)


def _case_unit_of_work(container: AppContainer) -> ClinicalCaseUnitOfWorkFactory:
    return cast(ClinicalCaseUnitOfWorkFactory, container.unit_of_work)


ContainerDependency = Annotated[AppContainer, Depends(_container)]
PatientCreateCommand = Annotated[
    CommandHeaders, Depends(command_headers_for(Permission.PATIENT_CREATE))
]
EncounterCreateCommand = Annotated[
    CommandHeaders, Depends(command_headers_for(Permission.ENCOUNTER_CREATE))
]
CaseCreateCommand = Annotated[
    CommandHeaders, Depends(command_headers_for(Permission.CLINICAL_CASE_CREATE))
]
PatientRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.PATIENT_READ))]
EncounterRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.ENCOUNTER_READ))]
CaseRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.CLINICAL_CASE_READ))]
TimelineRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TIMELINE_READ))]
AuditRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.AUDIT_READ))]


@router.post(
    "/patients",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["patients"],
    summary="Register a Patient reference",
    description="Persists a non-sensitive Patient reference, outbox event, and idempotency result.",
    responses=ERROR_RESPONSES,
)
def register_patient(
    body: RegisterPatientRequest, headers: PatientCreateCommand, container: ContainerDependency
) -> PatientResponse:
    summary = body.safe_demographic_summary
    result = RegisterPatientHandler(_patient_unit_of_work(container)).execute(
        RegisterPatient(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            patient_reference=body.patient_reference,
            safe_demographic_summary=SafeDemographicSummary(
                age_band=summary.age_band, sex_at_birth=summary.sex_at_birth
            ),
            requested_at=utc_now(),
        )
    )
    return _patient_response(result)


@router.get(
    "/patients/{patient_id}",
    response_model=PatientResponse,
    tags=["patients"],
    summary="Get a Patient",
    responses={404: ERROR_RESPONSES[404]},
)
def get_patient(
    patient_id: UUID, _authorization: PatientRead, container: ContainerDependency
) -> PatientResponse:
    return _patient_response(
        PatientQueryHandler(_patient_unit_of_work(container)).get_patient(GetPatient(patient_id))
    )


@router.post(
    "/encounters",
    response_model=EncounterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["encounters"],
    summary="Start an Encounter",
    description="Requires a persisted Patient and atomically records its lifecycle event.",
    responses=ERROR_RESPONSES,
)
def start_encounter(
    body: StartEncounterRequest, headers: EncounterCreateCommand, container: ContainerDependency
) -> EncounterResponse:
    result = StartEncounterHandler(_patient_unit_of_work(container)).execute(
        StartEncounter(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            patient_id=body.patient_id,
            location=body.location,
            arrival_at=body.arrival_at,
            external_reference=body.external_reference,
        )
    )
    return _encounter_response(result)


@router.get(
    "/encounters/{encounter_id}",
    response_model=EncounterResponse,
    tags=["encounters"],
    summary="Get an Encounter",
    responses={404: ERROR_RESPONSES[404]},
)
def get_encounter(
    encounter_id: UUID, _authorization: EncounterRead, container: ContainerDependency
) -> EncounterResponse:
    return _encounter_response(
        PatientQueryHandler(_patient_unit_of_work(container)).get_encounter(
            GetEncounter(encounter_id)
        )
    )


@router.post(
    "/clinical-cases",
    response_model=ClinicalCaseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["clinical-cases"],
    summary="Open a suspected ACS Clinical Case",
    description="Requires an Encounter and enforces one active case per encounter.",
    responses=ERROR_RESPONSES,
)
def open_clinical_case(
    body: OpenClinicalCaseRequest, headers: CaseCreateCommand, container: ContainerDependency
) -> ClinicalCaseResponse:
    result = OpenClinicalCaseHandler(_case_unit_of_work(container)).execute(
        OpenClinicalCase(
            command_id=uuid4(),
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
            encounter_id=body.encounter_id,
            opening_reason=body.opening_reason,
            priority=body.priority,
            requested_at=utc_now(),
        )
    )
    return _case_response(result)


@router.get(
    "/clinical-cases",
    response_model=PaginatedClinicalCasesResponse,
    tags=["clinical-cases"],
    summary="List active Clinical Cases",
)
def list_clinical_cases(
    container: ContainerDependency,
    _authorization: CaseRead,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    case_status: Annotated[CaseStatus | None, Query(alias="status")] = None,
    priority: ClinicalPriority | None = None,
    location: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
) -> PaginatedClinicalCasesResponse:
    result = ClinicalCaseQueryHandler(_case_unit_of_work(container)).list_active(
        ListActiveClinicalCases(
            page=page,
            page_size=page_size,
            status=case_status.value if case_status else None,
            priority=priority.value if priority else None,
            location=location,
        )
    )
    return _page_response(result)


@router.get(
    "/clinical-cases/{case_id}",
    response_model=ClinicalCaseResponse,
    tags=["clinical-cases"],
    summary="Get a Clinical Case",
    responses={404: ERROR_RESPONSES[404]},
)
def get_clinical_case(
    case_id: UUID, _authorization: CaseRead, container: ContainerDependency
) -> ClinicalCaseResponse:
    return _case_response(
        ClinicalCaseQueryHandler(_case_unit_of_work(container)).get(GetClinicalCase(case_id))
    )


@router.get(
    "/clinical-cases/{case_id}/timeline",
    response_model=list[TimelineEventResponse],
    tags=["timeline"],
    summary="Get the persisted Clinical Case lifecycle timeline",
    responses={404: ERROR_RESPONSES[404]},
)
def get_case_timeline(
    case_id: UUID, _authorization: TimelineRead, container: ContainerDependency
) -> list[TimelineEventResponse]:
    records = ClinicalCaseQueryHandler(_case_unit_of_work(container)).timeline(case_id)
    return [_timeline_response(record) for record in records]


@router.get(
    "/clinical-cases/{case_id}/audit",
    response_model=list[AuditEntryResponse],
    tags=["audit"],
    summary="Get immutable Patient, Encounter, and Case audit entries",
    responses={404: ERROR_RESPONSES[404]},
)
def get_case_audit(
    case_id: UUID, _authorization: AuditRead, container: ContainerDependency
) -> list[AuditEntryResponse]:
    records = ClinicalCaseQueryHandler(_case_unit_of_work(container)).audit(case_id)
    return [_audit_response(record) for record in records]


def _patient_response(value: PatientDTO) -> PatientResponse:
    return PatientResponse(
        patient_id=value.patient_id,
        patient_reference=value.patient_reference,
        reference_system=value.reference_system,
        safe_demographic_summary=SafeDemographicSummaryModel(
            age_band=value.safe_demographic_summary.age_band,
            sex_at_birth=value.safe_demographic_summary.sex_at_birth,
        ),
        created_at=value.created_at,
        updated_at=value.updated_at,
        aggregate_version=value.aggregate_version,
    )


def _encounter_response(value: EncounterDTO) -> EncounterResponse:
    return EncounterResponse(
        encounter_id=value.encounter_id,
        patient_id=value.patient_id,
        location=value.location,
        status=value.status,
        arrival_at=value.arrival_at,
        created_at=value.created_at,
        updated_at=value.updated_at,
        aggregate_version=value.aggregate_version,
    )


def _case_response(value: ClinicalCaseDTO) -> ClinicalCaseResponse:
    return ClinicalCaseResponse(
        case_id=value.case_id,
        encounter_id=value.encounter_id,
        opening_reason=value.opening_reason,
        priority=value.priority,
        status=value.status,
        opened_at=value.opened_at,
        updated_at=value.updated_at,
        aggregate_version=value.aggregate_version,
    )


def _page_response(value: ClinicalCasePageDTO) -> PaginatedClinicalCasesResponse:
    return PaginatedClinicalCasesResponse(
        items=[
            ClinicalCaseListItem(
                case_id=item.case_id,
                encounter_id=item.encounter_id,
                priority=item.priority,
                status=item.status,
                location=item.location,
                opened_at=item.opened_at,
                updated_at=item.updated_at,
                aggregate_version=item.aggregate_version,
            )
            for item in value.items
        ],
        page=value.page,
        page_size=value.page_size,
        total=value.total,
    )


def _timeline_response(value: TimelineReadRecord) -> TimelineEventResponse:
    return TimelineEventResponse(
        timeline_event_id=value.timeline_event_id,
        clinical_case_id=value.case_id,
        event_type=value.event_type,
        title=value.title,
        occurred_at=value.occurred_at,
        recorded_at=value.recorded_at,
        source=value.source,
        actor_id=value.actor_id,
        correlation_id=value.correlation_id,
        causation_id=value.causation_id,
    )


def _audit_response(value: AuditReadRecord) -> AuditEntryResponse:
    return AuditEntryResponse(
        audit_id=value.audit_id,
        actor_id=value.actor_id,
        actor_role=value.actor_role,
        identity_subject=value.identity_subject,
        actor_roles=value.actor_roles,
        applied_permission=value.applied_permission,
        identity_provider=value.identity_provider,
        authentication_method=value.authentication_method,
        session_reference=value.session_reference,
        action=value.action,
        resource_type=value.resource_type,
        resource_id=value.resource_id,
        request_source=value.request_source,
        correlation_id=value.correlation_id,
        causation_id=value.causation_id,
        prior_version=value.prior_version,
        resulting_version=value.resulting_version,
        outcome=value.outcome,
        reason=value.reason,
        recorded_at=value.recorded_at,
    )
