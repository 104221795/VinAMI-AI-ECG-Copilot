"""R7 application query service for the physician Command Center."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from vinami.clinical_case.ports.command_center import (
    CommandCenterCase,
    CommandCenterQuery,
    CommandCenterReadRepository,
)


class CommandCenterUnitOfWork(Protocol):
    """Minimal read-only transaction required by R7."""

    command_center: CommandCenterReadRepository

    def __enter__(self) -> CommandCenterUnitOfWork: ...

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Create an R7 read transaction."""

    def __call__(self) -> CommandCenterUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class ListCommandCenterCases:
    """Application-level queue request."""

    page: int
    page_size: int
    priority: str | None
    workflow_state: str | None
    overdue: bool | None
    alert_status: str | None
    evidence_status: str | None
    owner_id: UUID | None
    sort: str
    direction: str
    visible_locations: tuple[str, ...]
    now: datetime


@dataclass(frozen=True, slots=True)
class CommandCenterPage:
    """A stable page plus server-authoritative evaluation time."""

    items: tuple[CommandCenterCase, ...]
    page: int
    page_size: int
    total: int
    evaluated_at: datetime


class CommandCenterQueryService:
    """Coordinate the R7 projection inside one explicit read transaction."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def list_active(self, request: ListCommandCenterCases) -> CommandCenterPage:
        query = CommandCenterQuery(
            page=request.page,
            page_size=request.page_size,
            priority=request.priority,
            workflow_state=request.workflow_state,
            overdue=request.overdue,
            alert_status=request.alert_status,
            evidence_status=request.evidence_status,
            owner_id=request.owner_id,
            sort=request.sort,
            direction=request.direction,
            visible_locations=request.visible_locations,
            now=request.now,
        )
        with self._unit_of_work() as unit_of_work:
            items, total = unit_of_work.command_center.list_active(query)
        return CommandCenterPage(tuple(items), request.page, request.page_size, total, request.now)
