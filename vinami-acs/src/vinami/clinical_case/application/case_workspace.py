"""R8 application query for the complete physician case workspace."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.clinical_case.ports.case_workspace import (
    CaseWorkspaceReadRepository,
    CompleteCaseWorkspace,
)
from vinami.shared.application_errors import ResourceNotFoundError
from vinami.shared.domain import utc_now


class CaseWorkspaceUnitOfWork(Protocol):
    """Minimal transaction exposed to the R8 query service."""

    case_workspace: CaseWorkspaceReadRepository

    def __enter__(self) -> CaseWorkspaceUnitOfWork: ...

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> CaseWorkspaceUnitOfWork: ...


class CompleteCaseWorkspaceQueryService:
    """Return a location-scoped integrated view while preserving module authority."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def get(self, case_id: UUID, visible_locations: tuple[str, ...]) -> CompleteCaseWorkspace:
        with self._unit_of_work() as unit_of_work:
            result = unit_of_work.case_workspace.get(case_id, visible_locations, utc_now())
        if result is None:
            raise ResourceNotFoundError("clinical case was not found")
        return result
