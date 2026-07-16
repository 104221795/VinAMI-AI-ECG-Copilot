"""FastAPI delivery adapter for the R4 serial-troponin evidence workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from apps.api.http import AuthorizedIdentity, CommandHeaders, authorize_for, command_headers_for
from vinami.identity.domain.security import Permission
from vinami.shared.container import AppContainer
from vinami.troponin.application.service import RecordTroponinResult

router = APIRouter(prefix="/api/v1", tags=["troponin"])


class TroponinResultBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assay_code: str = Field(min_length=1, max_length=100)
    analyte: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=80, description="Base-10 decimal string")
    unit: str = Field(min_length=1, max_length=30)
    specimen_type: str = Field(min_length=1, max_length=80)
    specimen_collected_at: datetime
    resulted_at: datetime
    result_status: str
    reference_limit_value: str | None = None
    reference_limit_unit: str | None = None
    reference_limit_source: str | None = Field(default=None, max_length=240)
    quality_flags: list[str] = Field(default_factory=list, max_length=20)
    source_system: str = Field(min_length=1, max_length=160)
    source_result_id: str = Field(
        default_factory=lambda: f"manual-{uuid4()}", min_length=1, max_length=240
    )
    accession_number: str | None = Field(default=None, max_length=160)
    note: str | None = Field(default=None, max_length=2000)
    expected_case_version: int = Field(ge=1)


class TroponinAmendmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    unit: str
    result_status: str
    amendment_reason: str = Field(min_length=1, max_length=1000)
    resulted_at: datetime
    expected_version: int = Field(ge=1)


class TroponinImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connector_id: str = Field(min_length=1, max_length=120)
    external_reference: str = Field(min_length=1, max_length=240)
    expected_case_version: int = Field(ge=1)


class TroponinReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    referenced_result_ids: list[UUID] = Field(min_length=1)
    review_status: str = Field(min_length=1, max_length=80)
    incompatibility_acknowledged: bool = False
    quality_limitation_acknowledged: bool = False
    repeat_measurement_requested: bool = False
    repeat_measurement_reason: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime
    expected_case_version: int = Field(ge=1)


class TroponinReviewCorrectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correction_reason: str = Field(min_length=1, max_length=1000)
    referenced_result_ids: list[UUID] = Field(min_length=1)
    review_status: str = Field(min_length=1, max_length=80)
    incompatibility_acknowledged: bool = False
    quality_limitation_acknowledged: bool = False
    repeat_measurement_requested: bool = False
    repeat_measurement_reason: str | None = Field(default=None, max_length=1000)
    corrected_note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime
    expected_case_version: int = Field(ge=1)
    expected_review_version: int = Field(ge=1)


class TroponinRepeatTransitionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    completed_result_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)


class TroponinRetryImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.post("/clinical-cases/{case_id}/troponin-results", status_code=201)
def record_result(
    case_id: UUID,
    body: TroponinResultBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .troponin_application()
        .record_result(
            RecordTroponinResult(
                case_id=case_id,
                assay_code=body.assay_code,
                analyte=body.analyte,
                value=body.value,
                unit=body.unit,
                specimen_type=body.specimen_type,
                specimen_collected_at=body.specimen_collected_at,
                resulted_at=body.resulted_at,
                result_status=body.result_status,
                reference_limit_value=body.reference_limit_value,
                reference_limit_unit=body.reference_limit_unit,
                reference_limit_source=body.reference_limit_source,
                quality_flags=tuple(body.quality_flags),
                source_system=body.source_system,
                source_result_id=body.source_result_id,
                accession_number=body.accession_number,
                note=body.note,
                expected_case_version=body.expected_case_version,
                actor=headers.actor,
                idempotency_key=headers.idempotency_key,
            )
        )
    )


@router.get("/clinical-cases/{case_id}/troponin-results")
def list_results(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> list[dict[str, object]]:
    return _container(request).troponin_queries().workspace(case_id)["result_history"]  # type: ignore[return-value]


@router.get("/troponin-results/{result_id}")
def get_result(
    result_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> dict[str, object]:
    return _container(request).troponin_queries().result(result_id)


@router.post("/troponin-results/{result_id}/amendments", status_code=201)
def amend_result(
    result_id: UUID,
    body: TroponinAmendmentBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .troponin_application()
        .amend_result(
            result_id,
            value=body.value,
            unit=body.unit,
            status=body.result_status,
            reason=body.amendment_reason,
            resulted_at=body.resulted_at,
            expected_version=body.expected_version,
            actor=headers.actor,
            idempotency_key=headers.idempotency_key,
        )
    )


@router.get("/clinical-cases/{case_id}/troponin-series")
def get_series(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> dict[str, object]:
    workspace = _container(request).troponin_queries().workspace(case_id)
    return {
        "clinical_case_id": str(case_id),
        "effective_results": workspace["effective_results"],
        "latest_result": workspace["latest_result"],
    }


@router.get("/clinical-cases/{case_id}/troponin-deltas")
def get_deltas(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> dict[str, object]:
    return {
        "clinical_case_id": str(case_id),
        "deltas": _container(request).troponin_queries().workspace(case_id)["deltas"],
    }


@router.get("/clinical-cases/{case_id}/troponin-workspace")
def get_workspace(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> dict[str, object]:
    return _container(request).troponin_queries().workspace(case_id)


@router.post("/clinical-cases/{case_id}/troponin-imports", status_code=201)
def import_result(
    case_id: UUID,
    body: TroponinImportBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .troponin_application()
        .import_result(
            case_id,
            body.connector_id,
            body.external_reference,
            body.expected_case_version,
            headers.actor,
            headers.idempotency_key,
        )
    )


@router.get("/clinical-cases/{case_id}/troponin-imports")
def list_imports(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> list[dict[str, object]]:
    return _container(request).troponin_queries().workspace(case_id)["import_jobs"]  # type: ignore[return-value]


@router.get("/laboratory-import-jobs/{job_id}")
def get_import(
    job_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> dict[str, object]:
    return _container(request).troponin_queries().import_job(job_id)


@router.post("/laboratory-import-jobs/{job_id}/retry")
def retry_import(
    job_id: UUID,
    body: TroponinRetryImportBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .troponin_application()
        .retry_import(job_id, headers.actor, headers.idempotency_key, body.expected_version)
    )


@router.get("/troponin-assays")
def list_assays(
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> list[dict[str, object]]:
    return _container(request).troponin_queries().assays()


@router.get("/troponin-assays/{assay_id}")
def get_assay(
    assay_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> dict[str, object]:
    return _container(request).troponin_queries().assay(assay_id)


@router.get("/laboratory-connectors")
def list_connectors(
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> list[dict[str, object]]:
    return _container(request).troponin_queries().connectors()


@router.get("/laboratory-connectors/{connector_id}/health")
def connector_health(
    connector_id: str,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> dict[str, object]:
    return _container(request).troponin_queries().connector_health(connector_id)


@router.post("/clinical-cases/{case_id}/troponin-reviews", status_code=201)
def record_review(
    case_id: UUID,
    body: TroponinReviewBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_REVIEW))],
) -> dict[str, object]:
    return (
        _container(request)
        .troponin_application()
        .record_review(
            case_id,
            body.referenced_result_ids,
            body.review_status,
            body.incompatibility_acknowledged,
            body.quality_limitation_acknowledged,
            body.repeat_measurement_requested,
            body.repeat_measurement_reason,
            body.note,
            body.occurred_at,
            body.expected_case_version,
            headers.actor,
            headers.idempotency_key,
        )
    )


@router.post("/clinical-cases/{case_id}/troponin-reviews/{review_id}/corrections", status_code=201)
def correct_review(
    case_id: UUID,
    review_id: UUID,
    body: TroponinReviewCorrectionBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_REVIEW))],
) -> dict[str, object]:
    return (
        _container(request)
        .troponin_application()
        .correct_review(
            case_id,
            review_id,
            body.referenced_result_ids,
            body.review_status,
            body.incompatibility_acknowledged,
            body.quality_limitation_acknowledged,
            body.repeat_measurement_requested,
            body.repeat_measurement_reason,
            body.correction_reason,
            body.corrected_note,
            body.occurred_at,
            body.expected_case_version,
            body.expected_review_version,
            headers.actor,
            headers.idempotency_key,
        )
    )


@router.get("/clinical-cases/{case_id}/troponin-reviews")
def list_reviews(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> list[dict[str, object]]:
    return _container(request).troponin_queries().workspace(case_id)["clinician_reviews"]  # type: ignore[return-value]


@router.get("/clinical-cases/{case_id}/repeat-troponin-requests")
def list_repeat_requests(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.TROPONIN_READ))],
) -> list[dict[str, object]]:
    return _container(request).troponin_queries().workspace(case_id)["repeat_measurement_requests"]  # type: ignore[return-value]


def _repeat(
    action: str,
    request_id: UUID,
    body: TroponinRepeatTransitionBody,
    request: Request,
    headers: CommandHeaders,
) -> dict[str, object]:
    return (
        _container(request)
        .troponin_application()
        .transition_repeat(
            request_id,
            action,
            body.expected_version,
            headers.actor,
            headers.idempotency_key,
            body.completed_result_id,
            body.reason,
        )
    )


@router.post("/repeat-troponin-requests/{request_id}/acknowledge")
def acknowledge_repeat(
    request_id: UUID,
    body: TroponinRepeatTransitionBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_REVIEW))],
) -> dict[str, object]:
    return _repeat("acknowledge", request_id, body, request, headers)


@router.post("/repeat-troponin-requests/{request_id}/complete")
def complete_repeat(
    request_id: UUID,
    body: TroponinRepeatTransitionBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_REVIEW))],
) -> dict[str, object]:
    return _repeat("complete", request_id, body, request, headers)


@router.post("/repeat-troponin-requests/{request_id}/cancel")
def cancel_repeat(
    request_id: UUID,
    body: TroponinRepeatTransitionBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TROPONIN_REVIEW))],
) -> dict[str, object]:
    return _repeat("cancel", request_id, body, request, headers)
