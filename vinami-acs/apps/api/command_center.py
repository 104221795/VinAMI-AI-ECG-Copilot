"""FastAPI delivery adapter for the R7 Advanced Command Center."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from apps.api.http import AuthorizedIdentity, authorize_for
from vinami.clinical_case.application.command_center import ListCommandCenterCases
from vinami.clinical_case.ports.command_center import CommandCenterCase
from vinami.identity.domain.security import Permission
from vinami.shared.container import AppContainer
from vinami.shared.domain import utc_now
from vinami.workflow.domain.definition import WorkflowState

router = APIRouter(prefix="/api/v1/command-center", tags=["command-center"])


class CommandCenterTaskResponse(BaseModel):
    """Active R6 task summary."""

    model_config = ConfigDict(extra="forbid")
    task_id: UUID
    task_type: str
    status: str
    priority: str
    due_at: datetime | None
    overdue_at: datetime | None
    escalation_level: int
    owner_user_id: UUID | None
    owner_team_id: UUID | None


class CommandCenterAlertResponse(BaseModel):
    """Unresolved R6 alert summary."""

    model_config = ConfigDict(extra="forbid")
    alert_id: UUID
    alert_type: str
    source: str
    severity: str
    status: str
    raised_at: datetime
    escalation_level: int
    message: str


class CommandCenterCaseResponse(BaseModel):
    """One physician-facing operational queue row and quick-view payload."""

    model_config = ConfigDict(extra="forbid")
    case_id: UUID
    encounter_id: UUID
    patient_id: UUID
    patient_reference: str
    age_band: str | None
    sex_at_birth: str | None
    location: str
    case_status: str
    case_priority: str
    case_version: int
    opened_at: datetime
    workflow_id: UUID | None
    workflow_state: str | None
    workflow_version: int | None
    operational_priority: str
    priority_reason: str
    active_task_count: int
    overdue_task_count: int
    unresolved_alert_count: int
    next_due_at: datetime | None
    oldest_overdue_at: datetime | None
    owner_user_id: UUID | None
    owner_team_id: UUID | None
    snapshot_id: UUID | None
    snapshot_created_at: datetime | None
    evidence_status: str
    evidence_freshness: dict[str, str]
    missing_evidence: tuple[str, ...]
    technical_limits: tuple[str, ...]
    decision_id: UUID | None
    decision_type: str | None
    decision_rationale: str | None
    decision_recorded_at: datetime | None
    latest_activity_at: datetime
    update_token: str
    tasks: tuple[CommandCenterTaskResponse, ...]
    alerts: tuple[CommandCenterAlertResponse, ...]
    automation: dict[str, object]


class CommandCenterPageResponse(BaseModel):
    """Filtered and stably ordered active-case page."""

    model_config = ConfigDict(extra="forbid")
    items: tuple[CommandCenterCaseResponse, ...]
    page: int
    page_size: int
    total: int
    evaluated_at: datetime


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get("/cases", response_model=CommandCenterPageResponse)
def list_command_center_cases(
    request: Request,
    authorization: Annotated[
        AuthorizedIdentity, Depends(authorize_for(Permission.COMMAND_CENTER_READ))
    ],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    priority: Literal["routine", "urgent", "critical"] | None = None,
    workflow_state: WorkflowState | None = None,
    overdue: bool | None = None,
    alert_status: Literal["active", "acknowledged", "unresolved", "none"] | None = None,
    evidence_status: Literal["current", "missing", "stale", "technical_limit"] | None = None,
    owner_id: UUID | None = None,
    sort: Literal["priority", "opened_at", "next_due_at", "latest_activity"] = "priority",
    direction: Literal["asc", "desc"] = "desc",
) -> CommandCenterPageResponse:
    """Return only cases visible to the verified identity's location scope."""
    result = (
        _container(request)
        .command_center_queries()
        .list_active(
            ListCommandCenterCases(
                page,
                page_size,
                priority,
                workflow_state.value if workflow_state else None,
                overdue,
                alert_status,
                evidence_status,
                owner_id,
                sort,
                direction,
                authorization.identity.location_scope,
                utc_now(),
            )
        )
    )
    return CommandCenterPageResponse(
        items=tuple(_case_response(item) for item in result.items),
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        evaluated_at=result.evaluated_at,
    )


def _case_response(value: CommandCenterCase) -> CommandCenterCaseResponse:
    return CommandCenterCaseResponse(
        **{
            field: getattr(value, field)
            for field in CommandCenterCaseResponse.model_fields
            if field not in {"tasks", "alerts"}
        },
        tasks=tuple(
            CommandCenterTaskResponse.model_validate(task, from_attributes=True)
            for task in value.tasks
        ),
        alerts=tuple(
            CommandCenterAlertResponse.model_validate(alert, from_attributes=True)
            for alert in value.alerts
        ),
    )
