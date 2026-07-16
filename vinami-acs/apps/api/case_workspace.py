"""FastAPI delivery adapter for the R8 complete clinical case workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from apps.api.http import AuthorizedIdentity, authorize_for
from vinami.identity.domain.security import Permission
from vinami.shared.container import AppContainer

router = APIRouter(prefix="/api/v1/clinical-cases", tags=["case-workspace"])


class CompleteCaseWorkspaceResponse(BaseModel):
    """Integrated current-state projection with source provenance and no ORM leakage."""

    model_config = ConfigDict(extra="forbid")
    case_id: UUID
    encounter_id: UUID
    patient_id: UUID
    patient_reference: str
    patient_name: str | None
    age_band: str | None
    sex_at_birth: str | None
    location: str
    encounter_status: str
    case_status: str
    case_priority: str
    opening_reason: str
    opened_at: datetime
    last_updated_at: datetime
    case_version: int
    triage: dict[str, Any] | None
    vitals: dict[str, Any] | None
    ecg: dict[str, Any] | None
    troponin: dict[str, Any]
    evidence_snapshot: dict[str, Any] | None
    physician_assessment: dict[str, Any] | None
    physician_decision: dict[str, Any] | None
    workflow: dict[str, Any] | None
    tasks: tuple[dict[str, Any], ...]
    alerts: tuple[dict[str, Any], ...]
    timeline: tuple[dict[str, Any], ...]
    evidence_status: str
    missing_evidence: tuple[str, ...]
    stale_evidence: tuple[str, ...]
    technical_limits: tuple[str, ...]
    update_token: str
    evaluated_at: datetime


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get("/{case_id}/complete-workspace", response_model=CompleteCaseWorkspaceResponse)
def get_complete_case_workspace(
    case_id: UUID,
    request: Request,
    authorization: Annotated[
        AuthorizedIdentity, Depends(authorize_for(Permission.CLINICAL_CASE_READ))
    ],
) -> CompleteCaseWorkspaceResponse:
    """Return the visible effective case state from one backend projection."""
    value = (
        _container(request)
        .complete_case_workspace_queries()
        .get(case_id, authorization.identity.location_scope)
    )
    return CompleteCaseWorkspaceResponse.model_validate(value, from_attributes=True)
