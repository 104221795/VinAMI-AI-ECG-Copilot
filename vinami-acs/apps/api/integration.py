"""R10 real-time notifications and simulated hospital integration API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps.api.http import AuthorizedIdentity, CommandHeaders, authorize_for, command_headers_for
from vinami.identity.domain.security import Permission
from vinami.integration.application.reconciliation import classify_reconciliation
from vinami.integration.application.realtime import RealtimeNotification
from vinami.integration.application.service import SimulatedECGMessage, SimulatedLabMessage
from vinami.integration.domain.model import IntegrationMessage
from vinami.shared.container import AppContainer

router = APIRouter(prefix="/api/v1")


class RealtimeNotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    occurred_at: datetime
    case_id: UUID | None
    resource_hint: str
    correlation_id: UUID
    safety_notice: str


class IntegrationMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: UUID
    external_message_id: str
    source_system: str
    message_type: str
    schema_version: str
    clinical_case_id: UUID | None
    received_at: datetime
    processed_at: datetime | None
    status: str
    correlation_id: UUID
    causation_id: UUID | None
    retry_count: int
    validation_errors: tuple[str, ...]
    linked_record_ids: tuple[str, ...]
    dead_letter_reason: str | None
    simulated: bool
    record_version: int
    reconciliation_status: str
    reconciliation_reason: str
    review_required: bool
    safety_notice: str = (
        "Simulated integration messages are not physician decisions or workflow authority."
    )


class SimulatedLabResultBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_message_id: str = Field(min_length=1, max_length=240)
    source_system: str = Field(default="simulated-lis-r10", min_length=1, max_length=160)
    schema_version: str = Field(default="vinami-hl7-lab-result.v1", min_length=1, max_length=120)
    clinical_case_id: UUID
    assay_code: str = Field(default="DEMO-HS-CTNI-01", min_length=1, max_length=100)
    analyte: str = Field(default="cardiac_troponin_i", min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=30)
    specimen_type: str = Field(default="plasma", min_length=1, max_length=80)
    specimen_collected_at: datetime
    resulted_at: datetime
    result_status: str = Field(default="final", min_length=1, max_length=40)
    source_result_id: str = Field(min_length=1, max_length=240)
    expected_case_version: int = Field(ge=1)
    reference_limit_value: str | None = None
    reference_limit_unit: str | None = None
    reference_limit_source: str | None = None
    quality_flags: list[str] = Field(default_factory=list, max_length=20)
    accession_number: str | None = None
    note: str | None = None
    amendment_of_message_id: str | None = None
    amendment_reason: str | None = None
    failure_mode: str | None = Field(default=None, pattern="^temporary$")


class SimulatedECGMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_message_id: str = Field(min_length=1, max_length=240)
    source_system: str = Field(default="simulated-ecg-device-r10", min_length=1, max_length=160)
    schema_version: str = Field(default="vinami-ecg-device-study.v1", min_length=1, max_length=120)
    clinical_case_id: UUID
    study_reference: str = Field(min_length=1, max_length=240)
    acquisition_at: datetime
    expected_case_version: int = Field(ge=1)
    poor_quality: bool = False
    failure_mode: str | None = Field(default=None, pattern="^temporary$")


class RetryIntegrationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


Container = Annotated[AppContainer, Depends(_container)]
RealtimeRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.CLINICAL_CASE_READ))]
IntegrationRead = Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.INTEGRATION_READ))]
IntegrationWrite = Annotated[
    CommandHeaders, Depends(command_headers_for(Permission.INTEGRATION_WRITE))
]


@router.get(
    "/realtime/events",
    tags=["realtime"],
    summary="Server-sent backend notifications; clients must refetch authoritative APIs",
)
async def realtime_events(
    request: Request,
    container: Container,
    _: RealtimeRead,
    case_id: Annotated[UUID | None, Query()] = None,
) -> StreamingResponse:
    last_id = _uuid(request.headers.get("last-event-id"))

    async def stream() -> AsyncIterator[str]:
        nonlocal last_id
        yield ": vinami realtime stream connected\n\n"
        while not await request.is_disconnected():
            events = container.realtime_queries().events_since(last_id, case_id, limit=50)
            for item in events:
                last_id = item.event_id
                yield _sse(item)
            await asyncio.sleep(1.0)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/realtime/events/snapshot", response_model=list[RealtimeNotificationResponse])
def realtime_snapshot(
    container: Container,
    _: RealtimeRead,
    last_event_id: Annotated[UUID | None, Query()] = None,
    case_id: Annotated[UUID | None, Query()] = None,
) -> list[RealtimeNotificationResponse]:
    return [
        _notification(item)
        for item in container.realtime_queries().events_since(last_event_id, case_id, limit=50)
    ]


@router.get("/integration/messages", response_model=list[IntegrationMessageResponse])
def list_integration_messages(
    container: Container,
    _: IntegrationRead,
    status: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
    source_system: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    reconciliation_status: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[IntegrationMessageResponse]:
    responses = [
        _message(item)
        for item in container.integration_application().list_messages(
            status=status, source_system=source_system, limit=limit
        )
    ]
    if reconciliation_status:
        responses = [
            item
            for item in responses
            if item.reconciliation_status == reconciliation_status
        ]
    return responses


@router.get("/integration/connectors/status", response_model=dict[str, object])
def integration_connector_status(_: IntegrationRead) -> dict[str, object]:
    return {
        "connectors": [
            {
                "connector_id": "simulated-lis-r10",
                "kind": "laboratory",
                "status": "available",
                "simulated": True,
                "profile": "vinami-hl7-lab-result.v1",
            },
            {
                "connector_id": "simulated-ecg-device-r10",
                "kind": "ecg_device",
                "status": "available",
                "simulated": True,
                "profile": "vinami-ecg-device-study.v1",
            },
        ],
        "safety_notice": "No production LIS, HIS, EHR, PACS or device connection is configured.",
    }


@router.post(
    "/integration/simulated/laboratory-results",
    status_code=201,
    response_model=IntegrationMessageResponse,
)
def simulate_laboratory_result(
    body: SimulatedLabResultBody,
    container: Container,
    headers: IntegrationWrite,
) -> IntegrationMessageResponse:
    return _message(
        container.integration_application().receive_lab_result(
            SimulatedLabMessage(
                external_message_id=body.external_message_id,
                source_system=body.source_system,
                schema_version=body.schema_version,
                clinical_case_id=body.clinical_case_id,
                assay_code=body.assay_code,
                analyte=body.analyte,
                value=body.value,
                unit=body.unit,
                specimen_type=body.specimen_type,
                specimen_collected_at=body.specimen_collected_at,
                resulted_at=body.resulted_at,
                result_status=body.result_status,
                source_result_id=body.source_result_id,
                expected_case_version=body.expected_case_version,
                reference_limit_value=body.reference_limit_value,
                reference_limit_unit=body.reference_limit_unit,
                reference_limit_source=body.reference_limit_source,
                quality_flags=tuple(body.quality_flags),
                accession_number=body.accession_number,
                note=body.note,
                amendment_of_message_id=body.amendment_of_message_id,
                amendment_reason=body.amendment_reason,
                failure_mode=body.failure_mode,
            ),
            headers.actor,
            headers.idempotency_key,
        )
    )


@router.post(
    "/integration/simulated/ecg-studies",
    status_code=201,
    response_model=IntegrationMessageResponse,
)
def simulate_ecg_study(
    body: SimulatedECGMessageBody,
    container: Container,
    headers: IntegrationWrite,
) -> IntegrationMessageResponse:
    return _message(
        container.integration_application().receive_ecg_study(
            SimulatedECGMessage(
                external_message_id=body.external_message_id,
                source_system=body.source_system,
                schema_version=body.schema_version,
                clinical_case_id=body.clinical_case_id,
                study_reference=body.study_reference,
                acquisition_at=body.acquisition_at,
                expected_case_version=body.expected_case_version,
                poor_quality=body.poor_quality,
                failure_mode=body.failure_mode,
            ),
            headers.actor,
            headers.idempotency_key,
        )
    )


@router.post(
    "/integration/messages/{message_id}/retry",
    response_model=IntegrationMessageResponse,
)
def retry_integration_message(
    message_id: UUID,
    body: RetryIntegrationBody,
    container: Container,
    headers: IntegrationWrite,
) -> IntegrationMessageResponse:
    message = container.integration_application().retry_message(
        message_id, headers.actor, headers.idempotency_key
    )
    if message.record_version < body.expected_version:
        # The retry command is idempotent; stale client versions cannot make clinical decisions.
        return _message(message)
    return _message(message)


def _message(item: IntegrationMessage) -> IntegrationMessageResponse:
    reconciliation = classify_reconciliation(item)
    return IntegrationMessageResponse(
        message_id=item.message_id,
        external_message_id=item.external_message_id,
        source_system=item.source_system,
        message_type=item.message_type,
        schema_version=item.schema_version,
        clinical_case_id=item.clinical_case_id,
        received_at=item.received_at,
        processed_at=item.processed_at,
        status=item.status,
        correlation_id=item.correlation_id,
        causation_id=item.causation_id,
        retry_count=item.retry_count,
        validation_errors=item.validation_errors,
        linked_record_ids=item.linked_record_ids,
        dead_letter_reason=item.dead_letter_reason,
        simulated=item.simulated,
        record_version=item.record_version,
        reconciliation_status=str(reconciliation["reconciliation_status"]),
        reconciliation_reason=str(reconciliation["reconciliation_reason"]),
        review_required=bool(reconciliation["review_required"]),
    )


def _notification(item: RealtimeNotification) -> RealtimeNotificationResponse:
    return RealtimeNotificationResponse(
        event_id=item.event_id,
        event_type=item.event_type,
        aggregate_type=item.aggregate_type,
        aggregate_id=item.aggregate_id,
        occurred_at=item.occurred_at,
        case_id=item.case_id,
        resource_hint=item.resource_hint,
        correlation_id=item.correlation_id,
        safety_notice=item.safety_notice,
    )


def _sse(item: RealtimeNotification) -> str:
    data = json.dumps(
        _notification(item).model_dump(mode="json"),
        separators=(",", ":"),
    )
    return f"id: {item.event_id}\nevent: {item.resource_hint}\ndata: {data}\n\n"


def _uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
