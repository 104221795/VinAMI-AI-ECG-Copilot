"""R9 application services for case history, outcome and research export commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from vinami.audit.domain.model import Outcome
from vinami.audit.ports.history import CaseHistoryRepository, ModelProvenance, Page, ResearchExport
from vinami.shared.actor import ActorContext
from vinami.shared.application_errors import (
    IdempotencyConflictError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from vinami.shared.domain import require_text, require_utc, utc_now
from vinami.shared.events.contracts import EventEnvelope
from vinami.shared.idempotency import (
    IdempotencyRepository,
    IdempotencyResult,
    command_fingerprint,
)


class CaseHistoryUnitOfWork(Protocol):
    """Minimal transaction used by R9 services."""

    history: CaseHistoryRepository

    def __enter__(self) -> CaseHistoryUnitOfWork: ...

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None: ...

    def stage_event(self, event: EventEnvelope) -> None: ...

    def commit(self) -> None: ...


class IdempotentCaseHistoryUnitOfWork(CaseHistoryUnitOfWork, Protocol):
    idempotency: IdempotencyRepository


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> IdempotentCaseHistoryUnitOfWork: ...


@dataclass(frozen=True, slots=True)
class RecordOutcomeCommand:
    """Create the initial physician-authored outcome revision."""

    command_id: UUID
    case_id: UUID
    actor: ActorContext
    idempotency_key: str
    outcome_type: str
    outcome_timestamp: datetime
    final_conclusion: str
    disposition: str | None = None
    destination: str | None = None
    cath_lab_review_outcome: str | None = None
    intervention_reference: str | None = None
    complications: str | None = None
    follow_up_status: str | None = None
    data_completeness: str = "documented"
    source: str = "physician_documented"
    uncertainty: str | None = None
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class CorrectOutcomeCommand:
    """Append a corrected outcome revision without overwriting the prior one."""

    command_id: UUID
    case_id: UUID
    outcome_id: UUID
    actor: ActorContext
    idempotency_key: str
    correction_reason: str
    outcome_type: str
    outcome_timestamp: datetime
    final_conclusion: str
    disposition: str | None = None
    destination: str | None = None
    cath_lab_review_outcome: str | None = None
    intervention_reference: str | None = None
    complications: str | None = None
    follow_up_status: str | None = None
    data_completeness: str = "documented"
    source: str = "physician_documented"
    uncertainty: str | None = None
    unavailable_reason: str | None = None


@dataclass(frozen=True, slots=True)
class RequestResearchExportCommand:
    """Generate a synchronous MVP research export over authorized persisted cases."""

    command_id: UUID
    actor: ActorContext
    idempotency_key: str
    case_ids: tuple[UUID, ...]
    visible_locations: tuple[str, ...]


class CaseHistoryQueryService:
    """Read case history through the R9 repository and location scope."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def timeline(
        self,
        case_id: UUID,
        visible_locations: tuple[str, ...],
        page: int,
        page_size: int,
        event_type: str | None = None,
        correction_status: str | None = None,
    ) -> Page:
        with self._unit_of_work() as uow:
            _require_visible(uow.history, case_id, visible_locations)
            return uow.history.timeline(case_id, page, page_size, event_type, correction_status)

    def audit(
        self,
        case_id: UUID,
        visible_locations: tuple[str, ...],
        page: int,
        page_size: int,
        action: str | None = None,
        outcome: str | None = None,
    ) -> Page:
        with self._unit_of_work() as uow:
            _require_visible(uow.history, case_id, visible_locations)
            return uow.history.audit(case_id, page, page_size, action, outcome)

    def outcomes(self, case_id: UUID, visible_locations: tuple[str, ...]) -> tuple[Outcome, ...]:
        with self._unit_of_work() as uow:
            _require_visible(uow.history, case_id, visible_locations)
            return uow.history.outcome_history(case_id)

    def model_provenance(
        self, case_id: UUID, visible_locations: tuple[str, ...]
    ) -> tuple[ModelProvenance, ...]:
        with self._unit_of_work() as uow:
            _require_visible(uow.history, case_id, visible_locations)
            return uow.history.model_provenance(case_id)

    def research_export(self, export_id: UUID) -> ResearchExport:
        with self._unit_of_work() as uow:
            export = uow.history.get_research_export(export_id)
        if export is None:
            raise ResourceNotFoundError("research export was not found")
        return export


class CaseHistoryApplicationService:
    """Execute R9 consequential commands and publish only backend events."""

    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self._unit_of_work = unit_of_work

    def record_outcome(
        self, command: RecordOutcomeCommand, visible_locations: tuple[str, ...]
    ) -> Outcome:
        command.actor.require_physician()
        fingerprint = command_fingerprint(_command_payload(command))
        with self._unit_of_work() as uow:
            existing = _idempotent_result(
                uow, command.actor.actor_id, "RecordClinicalOutcome", command.idempotency_key
            )
            if existing:
                _require_same_payload(existing, fingerprint)
                outcome = uow.history.get_outcome(existing.resource_id)
                if outcome is None:
                    raise ResourceConflictError("stored outcome command result is unavailable")
                return outcome
            _require_visible(uow.history, command.case_id, visible_locations)
            if uow.history.latest_outcome(command.case_id) is not None:
                raise ResourceConflictError("clinical outcome already exists; create a correction")
            outcome = _outcome_from_record(command, revision_number=1)
            uow.history.add_outcome(outcome)
            _persist_command_result(
                uow,
                command.actor.actor_id,
                "RecordClinicalOutcome",
                command.idempotency_key,
                command.command_id,
                fingerprint,
                outcome.id,
                _outcome_payload(outcome),
            )
            uow.stage_event(_outcome_event("ClinicalOutcomeRecorded.v1", outcome, command.actor))
            uow.commit()
            return outcome

    def correct_outcome(
        self, command: CorrectOutcomeCommand, visible_locations: tuple[str, ...]
    ) -> Outcome:
        command.actor.require_physician()
        fingerprint = command_fingerprint(_command_payload(command))
        with self._unit_of_work() as uow:
            existing = _idempotent_result(
                uow, command.actor.actor_id, "CorrectClinicalOutcome", command.idempotency_key
            )
            if existing:
                _require_same_payload(existing, fingerprint)
                outcome = uow.history.get_outcome(existing.resource_id)
                if outcome is None:
                    raise ResourceConflictError("stored outcome correction result is unavailable")
                return outcome
            _require_visible(uow.history, command.case_id, visible_locations)
            target = uow.history.get_outcome(command.outcome_id)
            latest = uow.history.latest_outcome(command.case_id)
            if target is None or target.case_id != command.case_id:
                raise ResourceNotFoundError("clinical outcome revision was not found")
            if latest is None or latest.id != target.id:
                raise ResourceConflictError("only the latest outcome revision can be corrected")
            outcome = _outcome_from_correction(command, target)
            uow.history.add_outcome(outcome)
            _persist_command_result(
                uow,
                command.actor.actor_id,
                "CorrectClinicalOutcome",
                command.idempotency_key,
                command.command_id,
                fingerprint,
                outcome.id,
                _outcome_payload(outcome),
            )
            uow.stage_event(_outcome_event("ClinicalOutcomeCorrected.v1", outcome, command.actor))
            uow.commit()
            return outcome

    def request_research_export(self, command: RequestResearchExportCommand) -> ResearchExport:
        if not command.case_ids:
            raise ResourceConflictError("research export requires at least one case")
        fingerprint = command_fingerprint(_command_payload(command))
        with self._unit_of_work() as uow:
            existing = _idempotent_result(
                uow, command.actor.actor_id, "RequestResearchExport", command.idempotency_key
            )
            if existing:
                _require_same_payload(existing, fingerprint)
                export = uow.history.get_research_export(existing.resource_id)
                if export is None:
                    raise ResourceConflictError("stored export command result is unavailable")
                return export
            for case_id in command.case_ids:
                _require_visible(uow.history, case_id, command.visible_locations)
            export = uow.history.build_research_export(
                command.case_ids,
                command.actor.actor_id,
                command.actor.actor_role,
                command.idempotency_key,
                command.actor.correlation_id,
            )
            uow.history.add_research_export(export, command.idempotency_key)
            _persist_command_result(
                uow,
                command.actor.actor_id,
                "RequestResearchExport",
                command.idempotency_key,
                command.command_id,
                fingerprint,
                export.export_id,
                {"export_id": str(export.export_id), "checksum_sha256": export.checksum_sha256},
                resource_type="ResearchExport",
            )
            uow.stage_event(
                EventEnvelope(
                    event_type="ResearchExportCompleted.v1",
                    aggregate_type="ResearchExport",
                    aggregate_id=export.export_id,
                    aggregate_version=1,
                    actor_id=command.actor.actor_id,
                    correlation_id=command.actor.correlation_id,
                    causation_id=command.actor.causation_id,
                    payload={
                        "export_id": str(export.export_id),
                        "case_ids": [str(item) for item in export.case_ids],
                        "schema_version": export.schema_version,
                        "checksum_sha256": export.checksum_sha256,
                        "row_count": export.row_count,
                    },
                    metadata={
                        **command.actor.audit_metadata(),
                        "idempotency_key": command.idempotency_key,
                    },
                )
            )
            uow.commit()
            return export


def _require_visible(
    repository: CaseHistoryRepository, case_id: UUID, visible_locations: tuple[str, ...]
) -> None:
    if not repository.case_visible(case_id, visible_locations):
        raise ResourceNotFoundError("clinical case was not found")


def _idempotent_result(
    uow: IdempotentCaseHistoryUnitOfWork, actor_id: UUID, command_type: str, key: str
) -> IdempotencyResult | None:
    return uow.idempotency.lock_and_get(actor_id, command_type, key)


def _persist_command_result(
    uow: IdempotentCaseHistoryUnitOfWork,
    actor_id: UUID,
    command_type: str,
    key: str,
    command_id: UUID,
    fingerprint: str,
    resource_id: UUID,
    payload: dict[str, object],
    resource_type: str = "ClinicalOutcome",
) -> None:
    uow.idempotency.add(
        IdempotencyResult(
            actor_id=actor_id,
            command_type=command_type,
            idempotency_key=key,
            command_id=command_id,
            request_hash=fingerprint,
            resource_type=resource_type,
            resource_id=resource_id,
            response_payload=payload,
            created_at=utc_now(),
        )
    )


def _require_same_payload(previous: IdempotencyResult, fingerprint: str) -> None:
    if previous.request_hash != fingerprint:
        raise IdempotencyConflictError("idempotency key was already used for another payload")


def _outcome_from_record(command: RecordOutcomeCommand, revision_number: int) -> Outcome:
    return Outcome(
        case_id=command.case_id,
        outcome_type=command.outcome_type,
        outcome_timestamp=require_utc(command.outcome_timestamp, "outcome_timestamp"),
        final_conclusion=command.final_conclusion,
        recorded_at=utc_now(),
        recorded_by=command.actor.actor_id,
        actor_role=command.actor.actor_role,
        revision_number=revision_number,
        record_version=1,
        disposition=command.disposition,
        destination=command.destination,
        cath_lab_review_outcome=command.cath_lab_review_outcome,
        intervention_reference=command.intervention_reference,
        complications=command.complications,
        follow_up_status=command.follow_up_status,
        data_completeness=command.data_completeness,
        source=command.source,
        uncertainty=command.uncertainty,
        unavailable_reason=command.unavailable_reason,
        idempotency_key=command.idempotency_key,
        correlation_id=command.actor.correlation_id,
        causation_id=command.actor.causation_id,
    )


def _outcome_from_correction(command: CorrectOutcomeCommand, target: Outcome) -> Outcome:
    return Outcome(
        case_id=command.case_id,
        outcome_type=command.outcome_type,
        outcome_timestamp=require_utc(command.outcome_timestamp, "outcome_timestamp"),
        final_conclusion=command.final_conclusion,
        recorded_at=utc_now(),
        recorded_by=command.actor.actor_id,
        actor_role=command.actor.actor_role,
        revision_number=target.revision_number + 1,
        record_version=1,
        disposition=command.disposition,
        destination=command.destination,
        cath_lab_review_outcome=command.cath_lab_review_outcome,
        intervention_reference=command.intervention_reference,
        complications=command.complications,
        follow_up_status=command.follow_up_status,
        data_completeness=command.data_completeness,
        source=command.source,
        uncertainty=command.uncertainty,
        unavailable_reason=command.unavailable_reason,
        supersedes_outcome_id=target.id,
        correction_reason=require_text(command.correction_reason, "correction_reason"),
        idempotency_key=command.idempotency_key,
        correlation_id=command.actor.correlation_id,
        causation_id=command.actor.causation_id,
    )


def _outcome_event(event_type: str, outcome: Outcome, actor: ActorContext) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        aggregate_type="ClinicalOutcome",
        aggregate_id=outcome.id,
        aggregate_version=outcome.record_version,
        actor_id=actor.actor_id,
        correlation_id=actor.correlation_id,
        causation_id=actor.causation_id,
        occurred_at=outcome.recorded_at,
        payload={
            "case_id": str(outcome.case_id),
            "outcome_id": str(outcome.id),
            "revision_number": outcome.revision_number,
            "record_version": outcome.record_version,
            "outcome_type": outcome.outcome_type,
            "supersedes_outcome_id": (
                str(outcome.supersedes_outcome_id) if outcome.supersedes_outcome_id else None
            ),
            "correction_reason": outcome.correction_reason,
            "prior_version": outcome.revision_number - 1 if outcome.supersedes_outcome_id else None,
            "resulting_version": outcome.revision_number,
        },
        metadata={**actor.audit_metadata(), "idempotency_key": outcome.idempotency_key},
    )


def _outcome_payload(outcome: Outcome) -> dict[str, object]:
    return {
        "outcome_id": str(outcome.id),
        "case_id": str(outcome.case_id),
        "revision_number": outcome.revision_number,
    }


def _command_payload(command: object) -> dict[str, object]:
    document = asdict(command)
    document.pop("actor", None)
    document.pop("command_id", None)
    return document
