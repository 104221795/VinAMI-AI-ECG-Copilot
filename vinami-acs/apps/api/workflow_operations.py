"""FastAPI delivery adapter for R6 workflow, task, and alert operations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from apps.api.http import AuthorizedIdentity, CommandHeaders, authorize_for, command_headers_for
from vinami.identity.domain.security import Permission
from vinami.shared.container import AppContainer
from vinami.workflow.application.operations import (
    ChangeAlert,
    ChangeTask,
    EvaluateOverdueTasks,
    GenerateTaskFromDecision,
)
from vinami.workflow.domain.model import TaskPriority

router = APIRouter(prefix="/api/v1", tags=["workflow-operations"])


class GenerateTaskBody(BaseModel):
    """Request operational work from one persisted physician decision."""

    model_config = ConfigDict(extra="forbid")
    decision_id: UUID
    expected_decision_version: int = Field(ge=1)
    expected_workflow_version: int = Field(ge=1)
    priority: TaskPriority = TaskPriority.ROUTINE
    due_at: datetime | None = None


class TaskActionBody(BaseModel):
    """Optimistically versioned task transition request."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    owner_user_id: UUID | None = None
    owner_team_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=4000)


class AlertActionBody(BaseModel):
    """Optimistically versioned alert transition request."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=2000)


class OverdueEvaluationBody(BaseModel):
    """Request server-authoritative due-time evaluation."""

    model_config = ConfigDict(extra="forbid")


class TaskResponse(BaseModel):
    """Generated-client task contract."""

    model_config = ConfigDict(extra="forbid")
    task_id: UUID
    case_id: UUID
    workflow_id: UUID | None
    task_type: str
    status: str
    priority: str
    version: int
    created_at: datetime
    created_by: UUID | None
    due_at: datetime | None
    originating_decision_id: UUID | None
    source_type: str
    source_id: UUID | None
    owner_user_id: UUID | None
    owner_team_id: UUID | None
    acknowledged_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    outcome: str | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    overdue_at: datetime | None
    escalation_level: int
    history: list[dict[str, Any]]
    originating_decision: dict[str, Any] | None = None


class AlertResponse(BaseModel):
    """Generated-client operational alert contract."""

    model_config = ConfigDict(extra="forbid")
    alert_id: UUID
    case_id: UUID
    workflow_id: UUID | None
    task_id: UUID | None
    alert_type: str
    source: str
    severity: str
    message: str
    status: str
    version: int
    raised_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_reason: str | None
    escalation_level: int
    history: list[dict[str, Any]]


class WorkflowWorkspaceResponse(BaseModel):
    """Authoritative case-level R6 workspace contract."""

    model_config = ConfigDict(extra="forbid")
    case_id: UUID
    case_version: int
    workflow: dict[str, Any]
    tasks: list[TaskResponse]
    alerts: list[AlertResponse]
    safety_notice: str


def _container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


@router.get(
    "/clinical-cases/{case_id}/workflow-operations",
    response_model=WorkflowWorkspaceResponse,
)
def workspace(
    case_id: UUID,
    request: Request,
    _: Annotated[AuthorizedIdentity, Depends(authorize_for(Permission.WORKFLOW_READ))],
) -> dict[str, object]:
    return _container(request).workflow_operation_queries().workspace(case_id)


@router.post(
    "/clinical-cases/{case_id}/workflow-operations/tasks/from-decisions",
    response_model=TaskResponse,
    status_code=201,
)
def generate_task(
    case_id: UUID,
    body: GenerateTaskBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TASK_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .workflow_operations()
        .generate_task(
            GenerateTaskFromDecision(
                case_id,
                body.decision_id,
                body.expected_decision_version,
                body.expected_workflow_version,
                body.priority,
                body.due_at,
                headers.actor,
                headers.idempotency_key,
            )
        )
    )


@router.post(
    "/clinical-cases/{case_id}/workflow-operations/tasks/{task_id}/{action}",
    response_model=TaskResponse,
)
def change_task(
    case_id: UUID,
    task_id: UUID,
    action: Literal["assign", "acknowledge", "start", "complete", "cancel"],
    body: TaskActionBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TASK_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .workflow_operations()
        .change_task(
            ChangeTask(
                case_id,
                task_id,
                body.expected_version,
                action,
                headers.actor,
                headers.idempotency_key,
                body.owner_user_id,
                body.owner_team_id,
                body.reason,
            )
        )
    )


@router.post(
    "/clinical-cases/{case_id}/workflow-operations/overdue-evaluations",
    status_code=200,
)
def evaluate_overdue(
    case_id: UUID,
    _: OverdueEvaluationBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.TASK_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .workflow_operations()
        .evaluate_overdue(EvaluateOverdueTasks(case_id, headers.actor, headers.idempotency_key))
    )


@router.post(
    "/clinical-cases/{case_id}/workflow-operations/alerts/{alert_id}/{action}",
    response_model=AlertResponse,
)
def change_alert(
    case_id: UUID,
    alert_id: UUID,
    action: Literal["acknowledge", "resolve"],
    body: AlertActionBody,
    request: Request,
    headers: Annotated[CommandHeaders, Depends(command_headers_for(Permission.ALERT_WRITE))],
) -> dict[str, object]:
    return (
        _container(request)
        .workflow_operations()
        .change_alert(
            ChangeAlert(
                case_id,
                alert_id,
                body.expected_version,
                action,
                headers.actor,
                headers.idempotency_key,
                body.reason,
            )
        )
    )
