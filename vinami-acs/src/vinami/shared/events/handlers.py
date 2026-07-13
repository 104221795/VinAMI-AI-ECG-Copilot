"""Dependency-injected internal handlers for safe audit and timeline projections."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from vinami.audit.adapters.persistence import AuditLogRecord, OutboxEventRecord
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.ecg.adapters.persistence import ECGStudyRecord
from vinami.patient.adapters.persistence import EncounterRecord
from vinami.shared.domain import utc_now
from vinami.shared.events.contracts import EventEnvelope
from vinami.timeline.adapters.persistence import TimelineEventRecord


class EventHandler(Protocol):
    """One synchronous, transaction-bound event handler contract."""

    @property
    def name(self) -> str:
        """Expose a stable consumer-idempotency key."""
        ...

    @property
    def event_type(self) -> str:
        """Expose the event type accepted by this handler."""
        ...

    def handle(self, event: EventEnvelope, session: Session) -> None:
        """Apply one idempotent local projection or side effect."""


class HandlerRegistry:
    """Registry populated in the composition root rather than through module globals."""

    def __init__(self) -> None:
        """Create an empty handler registry."""
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def register(self, handler: EventHandler) -> None:
        """Register one handler for its declared event type."""
        self._handlers[handler.event_type].append(handler)

    def handlers_for(self, event: EventEnvelope) -> tuple[EventHandler, ...]:
        """Return a stable snapshot of handlers for one event envelope."""
        return tuple(self._handlers.get(event.event_type, []))


@dataclass(frozen=True, slots=True)
class TimelineAuditProjectionHandler:
    """Project one event to append-only audit/timeline rows without changing clinical state."""

    event_type: str

    @property
    def name(self) -> str:
        """Expose a stable idempotency key for this projection handler."""
        return f"timeline_audit_projection:{self.event_type}"

    def handle(self, event: EventEnvelope, session: Session) -> None:
        """Persist projection rows only when this source event has not been projected already."""
        case_id = _case_id(event, session)
        audit_exists = session.scalar(
            select(AuditLogRecord.id).where(AuditLogRecord.source_event_id == event.event_id)
        )
        if audit_exists is None:
            session.add(
                AuditLogRecord(
                    case_id=case_id,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    action=f"event:{event.event_type}",
                    actor_id=event.actor_id,
                    actor_role=(
                        str(event.metadata["actor_role"])
                        if event.metadata.get("actor_role") is not None
                        else None
                    ),
                    request_source=str(event.metadata.get("request_source", "internal")),
                    prior_version=_integer(event.payload.get("prior_version"))
                    or max(event.aggregate_version - 1, 0),
                    resulting_version=_integer(event.payload.get("resulting_version"))
                    or event.aggregate_version,
                    reason=(
                        str(event.payload["reason"])
                        if event.payload.get("reason") is not None
                        else None
                    ),
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    outcome="success",
                    occurred_at=event.occurred_at,
                    payload={
                        "event_version": event.event_version,
                        "correlation_id": str(event.correlation_id),
                        "causation_id": str(event.causation_id) if event.causation_id else None,
                        "payload": event.payload,
                        "metadata": event.metadata,
                    },
                    source_event_id=event.event_id,
                )
            )
        if case_id is None:
            return
        timeline_exists = session.scalar(
            select(TimelineEventRecord.id).where(
                TimelineEventRecord.case_id == case_id,
                TimelineEventRecord.source_event_id == event.event_id,
            )
        )
        if timeline_exists is None:
            session.add(
                TimelineEventRecord(
                    case_id=case_id,
                    event_type=event.event_type,
                    title=_event_title(event.event_type),
                    occurred_at=event.occurred_at,
                    recorded_at=utc_now(),
                    source="transactional_outbox",
                    actor_id=event.actor_id,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    payload={
                        "event_version": event.event_version,
                        "correlation_id": str(event.correlation_id),
                        "causation_id": str(event.causation_id) if event.causation_id else None,
                        "payload": event.payload,
                        "metadata": event.metadata,
                    },
                    source_event_id=event.event_id,
                )
            )
        if event.event_type == "ClinicalCaseOpened.v1":
            _project_case_ancestors(case_id, event, session)


def build_default_handler_registry() -> HandlerRegistry:
    """Register the initial catalog handlers through an explicit DI factory."""
    registry = HandlerRegistry()
    for event_type in (
        "PatientRegistered.v1",
        "EncounterStarted.v1",
        "ClinicalCaseOpened.v1",
        "SymptomsRecorded.v1",
        "VitalsRecorded.v1",
        "ECGUploaded.v1",
        "ECGQualityAssessed.v1",
        "AIAnalysisRequested.v1",
        "AIAnalysisCompleted.v1",
        "AIAnalysisFailed.v1",
        "TroponinOrdered.v1",
        "TroponinCollected.v1",
        "TroponinResulted.v1",
        "RepeatECGRequested.v1",
        "RepeatECGDue.v1",
        "ClinicalPathwaySuggested.v1",
        "WorkflowTransitioned.v1",
        "PhysicianReviewRequested.v1",
        "PhysicianDecisionRecorded.v1",
        "TaskCreated.v1",
        "TaskCompleted.v1",
        "AlertRaised.v1",
        "AlertAcknowledged.v1",
        "AlertResolved.v1",
        "CathLabReviewRequested.v1",
        "TransferRequested.v1",
        "CaseClosed.v1",
    ):
        registry.register(TimelineAuditProjectionHandler(event_type))
    return registry


def _case_id(event: EventEnvelope, session: Session) -> UUID | None:
    payload_case_id = event.payload.get("case_id")
    if isinstance(payload_case_id, str):
        try:
            return UUID(payload_case_id)
        except ValueError:
            return None
    if event.aggregate_type == "ClinicalCase":
        return event.aggregate_id
    study_id = event.payload.get("study_id")
    if isinstance(study_id, str):
        try:
            study = session.get(ECGStudyRecord, UUID(study_id))
        except ValueError:
            return None
        return study.case_id if study is not None else None
    return None


def _project_case_ancestors(case_id: UUID, event: EventEnvelope, session: Session) -> None:
    """Persist Patient and Encounter lifecycle events into a newly opened case timeline."""
    case_record = session.get(ClinicalCaseRecord, case_id)
    if case_record is None:
        return
    encounter = session.get(EncounterRecord, case_record.encounter_id)
    if encounter is None:
        return
    ancestor_events = session.scalars(
        select(OutboxEventRecord)
        .where(
            or_(
                (OutboxEventRecord.event_type == "PatientRegistered.v1")
                & (OutboxEventRecord.aggregate_id == encounter.patient_id),
                (OutboxEventRecord.event_type == "EncounterStarted.v1")
                & (OutboxEventRecord.aggregate_id == encounter.id),
            )
        )
        .order_by(OutboxEventRecord.occurred_at, OutboxEventRecord.event_id)
    ).all()
    for ancestor in ancestor_events:
        exists = session.scalar(
            select(TimelineEventRecord.id).where(
                TimelineEventRecord.case_id == case_id,
                TimelineEventRecord.source_event_id == ancestor.event_id,
            )
        )
        if exists is not None:
            continue
        session.add(
            TimelineEventRecord(
                case_id=case_id,
                event_type=ancestor.event_type,
                title=_event_title(ancestor.event_type),
                occurred_at=ancestor.occurred_at,
                recorded_at=utc_now(),
                source="transactional_outbox",
                actor_id=ancestor.actor_id,
                correlation_id=ancestor.correlation_id,
                causation_id=ancestor.causation_id,
                payload={
                    "event_version": ancestor.event_version,
                    "correlation_id": str(ancestor.correlation_id),
                    "causation_id": (str(ancestor.causation_id) if ancestor.causation_id else None),
                    "payload": ancestor.payload,
                    "metadata": ancestor.metadata_document,
                },
                source_event_id=ancestor.event_id,
            )
        )


def _event_title(event_type: str) -> str:
    return {
        "PatientRegistered.v1": "Patient registered",
        "EncounterStarted.v1": "Encounter started",
        "ClinicalCaseOpened.v1": "Suspected ACS case opened",
        "CaseClosed.v1": "Clinical case closed",
    }.get(event_type, event_type.removesuffix(".v1"))


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None


def registered_handler_names(registry: HandlerRegistry, event_types: Iterable[str]) -> set[str]:
    """Return handler names for diagnostics without exposing mutable registry internals."""
    names: set[str] = set()
    for event_type in event_types:
        envelope = EventEnvelope(
            event_type=event_type,
            aggregate_type="Diagnostic",
            aggregate_id=UUID(int=0),
            aggregate_version=1,
            payload={},
        )
        names.update(handler.name for handler in registry.handlers_for(envelope))
    return names
