"""Application commands and queries for the suspected ACS Clinical Case lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from vinami.clinical_case.domain.model import ClinicalCase, ClinicalPriority
from vinami.clinical_case.ports.read_models import (
    AuditReadRecord,
    ClinicalLifecycleReadRepository,
    TimelineReadRecord,
)
from vinami.clinical_case.ports.repository import ClinicalCaseRepository
from vinami.patient.application.lifecycle import ActorRepository
from vinami.patient.ports.repository import EncounterRepository
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import (
    ActorContextError,
    IdempotencyConflictError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from vinami.shared.domain import require_text, require_utc
from vinami.shared.events.contracts import EventContext
from vinami.shared.idempotency import (
    IdempotencyRepository,
    IdempotencyResult,
    command_fingerprint,
)
from vinami.workflow.application.definitions import load_demo_workflow_definition
from vinami.workflow.domain.model import ClinicalWorkflow
from vinami.workflow.ports.repository import ClinicalWorkflowRepository


class ClinicalCaseUnitOfWork(Protocol):
    """Minimal transaction port required by R1 case commands and queries."""

    encounters: EncounterRepository
    cases: ClinicalCaseRepository
    lifecycle_reads: ClinicalLifecycleReadRepository
    actors: ActorRepository
    idempotency: IdempotencyRepository
    workflows: ClinicalWorkflowRepository

    def __enter__(self) -> ClinicalCaseUnitOfWork: ...

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None: ...

    def collect_events(self, aggregates: list[ClinicalCase]) -> None: ...

    def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Create one transaction for a case command or query."""

    def __call__(self) -> ClinicalCaseUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class ClinicalCaseDTO:
    """Application representation of one persisted Clinical Case."""

    case_id: UUID
    encounter_id: UUID
    opening_reason: str
    priority: str
    status: str
    opened_at: datetime
    updated_at: datetime
    aggregate_version: int

    def to_document(self) -> dict[str, Any]:
        """Serialize for persistent idempotency."""
        return {
            "case_id": str(self.case_id),
            "encounter_id": str(self.encounter_id),
            "opening_reason": self.opening_reason,
            "priority": self.priority,
            "status": self.status,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "aggregate_version": self.aggregate_version,
        }

    @classmethod
    def from_document(cls, value: dict[str, Any]) -> ClinicalCaseDTO:
        """Rehydrate an original idempotent response."""
        return cls(
            case_id=UUID(str(value["case_id"])),
            encounter_id=UUID(str(value["encounter_id"])),
            opening_reason=str(value["opening_reason"]),
            priority=str(value["priority"]),
            status=str(value["status"]),
            opened_at=datetime.fromisoformat(str(value["opened_at"])),
            updated_at=datetime.fromisoformat(str(value["updated_at"])),
            aggregate_version=int(value["aggregate_version"]),
        )


@dataclass(frozen=True, slots=True)
class ClinicalCaseListItemDTO:
    """Queue projection combining case-owned facts with encounter location."""

    case_id: UUID
    encounter_id: UUID
    priority: str
    status: str
    location: str
    opened_at: datetime
    updated_at: datetime
    aggregate_version: int


@dataclass(frozen=True, slots=True)
class ClinicalCasePageDTO:
    """Deterministic page of active Clinical Cases."""

    items: tuple[ClinicalCaseListItemDTO, ...]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True, slots=True)
class OpenClinicalCase:
    """Open one suspected ACS case for an existing Encounter."""

    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    encounter_id: UUID
    opening_reason: str
    priority: ClinicalPriority
    requested_at: datetime
    case_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "idempotency_key", require_text(self.idempotency_key, "idempotency_key")
        )
        object.__setattr__(
            self, "opening_reason", require_text(self.opening_reason, "opening_reason")
        )
        object.__setattr__(self, "requested_at", require_utc(self.requested_at, "requested_at"))


@dataclass(frozen=True, slots=True)
class GetClinicalCase:
    """Retrieve one Clinical Case by public UUID."""

    case_id: UUID


@dataclass(frozen=True, slots=True)
class ListActiveClinicalCases:
    """Filter and page the active-case queue."""

    page: int = 1
    page_size: int = 25
    status: str | None = None
    priority: str | None = None
    location: str | None = None


class OpenClinicalCaseHandler:
    """Coordinate case opening with parent and duplicate-active-case checks."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def execute(self, command: OpenClinicalCase) -> ClinicalCaseDTO:
        payload = {
            "encounter_id": str(command.encounter_id),
            "opening_reason": command.opening_reason,
            "priority": command.priority.value,
        }
        fingerprint = command_fingerprint(payload)
        with self._unit_of_work() as unit_of_work:
            if unit_of_work.actors.role_for(command.actor.actor_id) != command.actor.actor_role:
                raise ActorContextError(
                    "development actor reference is unknown or role does not match"
                )
            previous = unit_of_work.idempotency.lock_and_get(
                command.actor.actor_id, "OpenClinicalCase", command.idempotency_key
            )
            if previous is not None:
                if previous.request_hash != fingerprint:
                    raise IdempotencyConflictError(
                        "idempotency key was already used for another payload"
                    )
                return ClinicalCaseDTO.from_document(previous.response_payload)
            if unit_of_work.encounters.get(command.encounter_id) is None:
                raise ResourceNotFoundError("encounter not found")
            if unit_of_work.cases.get_active_for_encounter(command.encounter_id) is not None:
                raise ResourceConflictError("encounter already has an active clinical case")
            clinical_case = ClinicalCase.open(
                command.encounter_id,
                command.opening_reason,
                command.priority,
                command.requested_at,
                case_id=command.case_id,
                context=EventContext(
                    correlation_id=command.actor.correlation_id,
                    causation_id=command.actor.causation_id,
                    actor_id=command.actor.actor_id,
                    metadata=command.actor.audit_metadata(),
                ),
            )
            response = _case_dto(clinical_case)
            unit_of_work.cases.add(clinical_case)
            unit_of_work.workflows.add(
                ClinicalWorkflow.start(clinical_case.id, load_demo_workflow_definition())
            )
            unit_of_work.collect_events([clinical_case])
            unit_of_work.idempotency.add(
                IdempotencyResult(
                    actor_id=command.actor.actor_id,
                    command_type="OpenClinicalCase",
                    idempotency_key=command.idempotency_key,
                    command_id=command.command_id,
                    request_hash=fingerprint,
                    resource_type="ClinicalCase",
                    resource_id=clinical_case.id,
                    response_payload=response.to_document(),
                    created_at=command.requested_at,
                )
            )
            unit_of_work.commit()
            return response


class ClinicalCaseQueryHandler:
    """Read case aggregates and persisted lifecycle projections through ports."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def get(self, query: GetClinicalCase) -> ClinicalCaseDTO:
        with self._unit_of_work() as unit_of_work:
            clinical_case = unit_of_work.cases.get(query.case_id)
            if clinical_case is None:
                raise ResourceNotFoundError("clinical case not found")
            return _case_dto(clinical_case)

    def list_active(self, query: ListActiveClinicalCases) -> ClinicalCasePageDTO:
        with self._unit_of_work() as unit_of_work:
            rows, total = unit_of_work.cases.list_active(
                offset=(query.page - 1) * query.page_size,
                limit=query.page_size,
                status=query.status,
                priority=query.priority,
                location=query.location,
            )
            return ClinicalCasePageDTO(
                items=tuple(
                    ClinicalCaseListItemDTO(
                        case_id=row.clinical_case.id,
                        encounter_id=row.clinical_case.encounter_id,
                        priority=row.clinical_case.priority.value,
                        status=row.clinical_case.status.value,
                        location=row.location,
                        opened_at=row.clinical_case.opened_at,
                        updated_at=row.clinical_case.updated_at or row.clinical_case.opened_at,
                        aggregate_version=row.clinical_case.version,
                    )
                    for row in rows
                ),
                page=query.page,
                page_size=query.page_size,
                total=total,
            )

    def timeline(self, case_id: UUID) -> tuple[TimelineReadRecord, ...]:
        with self._unit_of_work() as unit_of_work:
            if unit_of_work.cases.get(case_id) is None:
                raise ResourceNotFoundError("clinical case not found")
            return tuple(unit_of_work.lifecycle_reads.timeline_for_case(case_id))

    def audit(self, case_id: UUID) -> tuple[AuditReadRecord, ...]:
        with self._unit_of_work() as unit_of_work:
            if unit_of_work.cases.get(case_id) is None:
                raise ResourceNotFoundError("clinical case not found")
            return tuple(unit_of_work.lifecycle_reads.audit_for_case(case_id))


def _case_dto(clinical_case: ClinicalCase) -> ClinicalCaseDTO:
    return ClinicalCaseDTO(
        case_id=clinical_case.id,
        encounter_id=clinical_case.encounter_id,
        opening_reason=clinical_case.opening_reason,
        priority=clinical_case.priority.value,
        status=clinical_case.status.value,
        opened_at=clinical_case.opened_at,
        updated_at=clinical_case.updated_at or clinical_case.opened_at,
        aggregate_version=clinical_case.version,
    )
