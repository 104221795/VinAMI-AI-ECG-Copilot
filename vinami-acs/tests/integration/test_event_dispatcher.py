"""PostgreSQL reliability tests for the internal transactional-outbox dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from vinami.audit.adapters.persistence import EventConsumptionRecord, OutboxEventRecord
from vinami.shared.domain import AggregateRoot
from vinami.shared.events.contracts import EventContext, EventEnvelope, OutboxStatus
from vinami.shared.events.dispatcher import InternalEventDispatcher, ReplayRequest
from vinami.shared.events.handlers import (
    HandlerRegistry,
    build_default_handler_registry,
    registered_handler_names,
)
from vinami.shared.events.registry import EventRegistry
from vinami.shared.events.serializer import EventSerializer
from vinami.shared.unit_of_work import SQLAlchemyUnitOfWork

NOW = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)


@dataclass(slots=True)
class SampleAggregate(AggregateRoot):
    """Minimal aggregate used only to verify Unit of Work envelope persistence."""


@dataclass(slots=True)
class CountingHandler:
    """Deterministic handler whose counter reveals duplicate deliveries."""

    event_type: str
    name: str
    calls: int = 0

    def handle(self, event: EventEnvelope, session: Session) -> None:
        """Record one invocation without changing clinical aggregate state."""
        _ = event, session
        self.calls += 1


@dataclass(slots=True)
class FailingHandler:
    """Deterministic poison handler used to verify retry and dead-letter behavior."""

    event_type: str
    name: str

    def handle(self, event: EventEnvelope, session: Session) -> None:
        """Fail every attempt after accepting the dispatcher transaction parameters."""
        _ = event, session
        raise RuntimeError("intentional handler failure")


@pytest.fixture(autouse=True)
def clear_event_delivery_state(postgres_session_factory: sessionmaker[Session]) -> None:
    """Keep each dispatcher test independent despite the session-scoped PostgreSQL fixture."""
    with postgres_session_factory() as session:
        session.execute(delete(EventConsumptionRecord))
        session.execute(delete(OutboxEventRecord))
        session.commit()


def _dispatcher(
    session_factory: sessionmaker[Session],
    handlers: HandlerRegistry,
    max_retries: int = 3,
) -> InternalEventDispatcher:
    return InternalEventDispatcher(
        session_factory=session_factory,
        serializer=EventSerializer(EventRegistry.default()),
        handlers=handlers,
        logger=structlog.get_logger("event-test"),
        max_retries=max_retries,
        retry_delay_seconds=0,
        claim_ttl_seconds=60,
    )


def _event(event_type: str = "ClinicalCaseOpened.v1") -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        aggregate_type="ClinicalCase",
        aggregate_id=uuid4(),
        aggregate_version=1,
        occurred_at=NOW,
        correlation_id=uuid4(),
        payload={"case_id": str(uuid4())},
    )


def _store_event(session_factory: sessionmaker[Session], event: EventEnvelope) -> None:
    with session_factory() as session:
        session.add(
            OutboxEventRecord(
                event_id=event.event_id,
                event_type=event.event_type,
                event_version=event.event_version,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                aggregate_version=event.aggregate_version,
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                actor_id=event.actor_id,
                payload=event.payload,
                metadata_document=event.metadata,
                status=OutboxStatus.PENDING.value,
                available_at=NOW,
            )
        )
        session.commit()


def test_unit_of_work_persists_event_and_aggregate_change_atomically_with_context(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Envelope provenance is committed with its aggregate change in one transaction."""
    aggregate = SampleAggregate(id=uuid4())
    context = EventContext(correlation_id=uuid4(), causation_id=uuid4(), actor_id=uuid4())
    aggregate._record_event("ClinicalCaseOpened.v1", 1, {"case_id": str(aggregate.id)}, context)

    with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
        uow.collect_events([aggregate])
        uow.commit()

    with postgres_session_factory() as session:
        record = session.scalar(
            select(OutboxEventRecord).where(OutboxEventRecord.aggregate_id == aggregate.id)
        )
        assert record is not None
        assert record.correlation_id == context.correlation_id
        assert record.causation_id == context.causation_id
        assert record.actor_id == context.actor_id
        assert record.event_version == 1


def test_duplicate_delivery_does_not_repeat_handler_side_effect(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """The consumer ledger skips a handler already completed for the same event ID."""
    event = _event()
    _store_event(postgres_session_factory, event)
    handler = CountingHandler(event.event_type, "counting-handler")
    handlers = HandlerRegistry()
    handlers.register(handler)
    dispatcher = _dispatcher(postgres_session_factory, handlers)

    assert dispatcher.dispatch_pending().published == 1
    with postgres_session_factory() as session:
        session.execute(
            update(OutboxEventRecord)
            .where(OutboxEventRecord.event_id == event.event_id)
            .values(status=OutboxStatus.PENDING.value, available_at=NOW)
        )
        session.commit()
    assert dispatcher.dispatch_pending().published == 1
    assert handler.calls == 1
    with postgres_session_factory() as session:
        consumptions = session.scalars(
            select(EventConsumptionRecord).where(EventConsumptionRecord.event_id == event.event_id)
        ).all()
        assert len(consumptions) == 1


def test_poison_event_retries_then_moves_to_dead_letter(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """A handler failure persists retry state and finally a visible dead-letter state."""
    event = _event()
    _store_event(postgres_session_factory, event)
    handlers = HandlerRegistry()
    handlers.register(FailingHandler(event.event_type, "failing-handler"))
    dispatcher = _dispatcher(postgres_session_factory, handlers, max_retries=2)

    assert dispatcher.dispatch_pending().retried == 1
    assert dispatcher.dispatch_pending().dead_lettered == 1
    with postgres_session_factory() as session:
        record = session.scalar(
            select(OutboxEventRecord).where(OutboxEventRecord.event_id == event.event_id)
        )
        assert record is not None
        assert record.delivery_attempts == 2
        assert record.status == OutboxStatus.DEAD_LETTER.value
        assert record.is_dead_letter is True


def test_replay_resets_selected_events_and_reprocesses_handlers(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Replay clears the selected consumer ledger while source projections remain idempotent."""
    event = _event()
    _store_event(postgres_session_factory, event)
    handler = CountingHandler(event.event_type, "replay-handler")
    handlers = HandlerRegistry()
    handlers.register(handler)
    dispatcher = _dispatcher(postgres_session_factory, handlers)

    assert dispatcher.dispatch_pending().published == 1
    replayed = dispatcher.replay(ReplayRequest((event.event_type,), NOW, NOW))
    assert replayed == 1
    assert dispatcher.dispatch_pending().published == 1
    assert handler.calls == 2


def test_initial_handler_registration_covers_the_approved_event_set() -> None:
    """All ten Sprint 4 event types receive an explicit DI-registered initial handler."""
    event_types = (
        "ClinicalCaseOpened.v1",
        "ECGUploaded.v1",
        "AIAnalysisCompleted.v1",
        "TroponinResulted.v1",
        "RepeatECGDue.v1",
        "ClinicalPathwaySuggested.v1",
        "PhysicianDecisionRecorded.v1",
        "TaskCreated.v1",
        "AlertRaised.v1",
        "CaseClosed.v1",
    )
    names = registered_handler_names(build_default_handler_registry(), event_types)
    assert len(names) == len(event_types)
