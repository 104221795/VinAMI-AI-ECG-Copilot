"""PostgreSQL-backed at-least-once internal dispatcher with replay and dead-letter handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from vinami.audit.adapters.persistence import EventConsumptionRecord, OutboxEventRecord
from vinami.shared.events.contracts import OutboxStatus
from vinami.shared.events.handlers import HandlerRegistry
from vinami.shared.events.serializer import EventSerializer
from vinami.shared.logging import log_event


@dataclass(frozen=True, slots=True)
class DispatchSummary:
    """Outcome counters for one dispatcher polling cycle."""

    published: int = 0
    retried: int = 0
    dead_lettered: int = 0
    skipped: int = 0


@dataclass(frozen=True, slots=True)
class ReplayRequest:
    """Selected event types and UTC interval for an intentional internal replay."""

    event_types: tuple[str, ...]
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        """Require a non-empty event selection and an ordered UTC interval."""
        if not self.event_types:
            raise ValueError("replay requires at least one event type")
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("replay interval must be timezone-aware")
        if self.end_at < self.start_at:
            raise ValueError("replay end_at cannot precede start_at")


class InternalEventDispatcher:
    """Deliver committed outbox events through idempotent handlers and database transactions."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        serializer: EventSerializer,
        handlers: HandlerRegistry,
        logger: structlog.stdlib.BoundLogger,
        max_retries: int,
        retry_delay_seconds: float,
        claim_ttl_seconds: float,
    ) -> None:
        """Receive replaceable persistence, serialization, handler, and retry dependencies."""
        if max_retries < 1:
            raise ValueError("max_retries must be at least one")
        self._session_factory = session_factory
        self._serializer = serializer
        self._handlers = handlers
        self._logger = logger
        self._max_retries = max_retries
        self._retry_delay = timedelta(seconds=retry_delay_seconds)
        self._claim_ttl = timedelta(seconds=claim_ttl_seconds)

    def dispatch_pending(self, limit: int = 100) -> DispatchSummary:
        """Claim due rows one by one and deliver each with at-least-once semantics."""
        if limit < 1:
            raise ValueError("limit must be at least one")
        event_ids = self._due_event_ids(limit)
        summary = DispatchSummary()
        for event_id in event_ids:
            outcome = self._deliver(event_id)
            if outcome == "published":
                summary = DispatchSummary(
                    published=summary.published + 1,
                    retried=summary.retried,
                    dead_lettered=summary.dead_lettered,
                    skipped=summary.skipped,
                )
            elif outcome == "retried":
                summary = DispatchSummary(
                    published=summary.published,
                    retried=summary.retried + 1,
                    dead_lettered=summary.dead_lettered,
                    skipped=summary.skipped,
                )
            elif outcome == "dead_lettered":
                summary = DispatchSummary(
                    published=summary.published,
                    retried=summary.retried,
                    dead_lettered=summary.dead_lettered + 1,
                    skipped=summary.skipped,
                )
            else:
                summary = DispatchSummary(
                    published=summary.published,
                    retried=summary.retried,
                    dead_lettered=summary.dead_lettered,
                    skipped=summary.skipped + 1,
                )
        return summary

    def replay(self, request: ReplayRequest) -> int:
        """Reset selected events and consumer ledger rows for an intentional replay."""
        now = datetime.now(UTC)
        with self._session_factory() as session:
            event_ids = list(
                session.scalars(
                    select(OutboxEventRecord.event_id).where(
                        OutboxEventRecord.event_type.in_(request.event_types),
                        OutboxEventRecord.occurred_at >= request.start_at.astimezone(UTC),
                        OutboxEventRecord.occurred_at <= request.end_at.astimezone(UTC),
                    )
                )
            )
            if not event_ids:
                return 0
            session.execute(
                delete(EventConsumptionRecord).where(EventConsumptionRecord.event_id.in_(event_ids))
            )
            session.execute(
                update(OutboxEventRecord)
                .where(OutboxEventRecord.event_id.in_(event_ids))
                .values(
                    status=OutboxStatus.PENDING.value,
                    available_at=now,
                    claimed_at=None,
                    published_at=None,
                    last_error=None,
                    is_dead_letter=False,
                    delivery_attempts=0,
                )
            )
            session.commit()
        log_event(
            self._logger,
            "event_replay_requested",
            event_types=list(request.event_types),
            start_at=request.start_at.isoformat(),
            end_at=request.end_at.isoformat(),
            replayed=len(event_ids),
        )
        return len(event_ids)

    def _due_event_ids(self, limit: int) -> list[UUID]:
        now = datetime.now(UTC)
        stale_before = now - self._claim_ttl
        with self._session_factory() as session:
            statement = (
                select(OutboxEventRecord.event_id)
                .where(
                    or_(
                        and_(
                            OutboxEventRecord.status == OutboxStatus.PENDING.value,
                            OutboxEventRecord.available_at <= now,
                        ),
                        and_(
                            OutboxEventRecord.status == OutboxStatus.PROCESSING.value,
                            OutboxEventRecord.claimed_at < stale_before,
                        ),
                    )
                )
                .order_by(OutboxEventRecord.occurred_at, OutboxEventRecord.event_id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            return list(session.scalars(statement))

    def _deliver(self, event_id: UUID) -> str:
        session = self._session_factory()
        try:
            record = session.scalar(
                select(OutboxEventRecord)
                .where(OutboxEventRecord.event_id == event_id)
                .with_for_update(skip_locked=True)
            )
            if record is None or record.status in {
                OutboxStatus.PUBLISHED.value,
                OutboxStatus.DEAD_LETTER.value,
            }:
                session.rollback()
                return "skipped"
            now = datetime.now(UTC)
            record.status = OutboxStatus.PROCESSING.value
            record.claimed_at = now
            record.last_attempt_at = now
            event = self._serializer.deserialize(self._document(record))
            handled_count = 0
            for handler in self._handlers.handlers_for(event):
                consumed = session.scalar(
                    select(EventConsumptionRecord.id).where(
                        EventConsumptionRecord.event_id == event.event_id,
                        EventConsumptionRecord.handler_name == handler.name,
                    )
                )
                if consumed is not None:
                    continue
                handler.handle(event, session)
                session.add(
                    EventConsumptionRecord(
                        event_id=event.event_id,
                        handler_name=handler.name,
                        consumed_at=now,
                    )
                )
                handled_count += 1
            record.delivery_attempts += 1
            record.status = OutboxStatus.PUBLISHED.value
            record.published_at = now
            record.claimed_at = None
            record.last_error = None
            record.is_dead_letter = False
            session.commit()
            log_event(
                self._logger,
                "event_published",
                event_id=str(event.event_id),
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
                causation_id=str(event.causation_id) if event.causation_id else None,
                handlers=handled_count,
            )
            return "published"
        except Exception as error:
            session.rollback()
            return self._record_failure(event_id, error)
        finally:
            session.close()

    def _record_failure(self, event_id: UUID, error: Exception) -> str:
        """Persist retry/dead-letter state separately after handler transaction rollback."""
        now = datetime.now(UTC)
        with self._session_factory() as session:
            record = session.scalar(
                select(OutboxEventRecord)
                .where(OutboxEventRecord.event_id == event_id)
                .with_for_update(skip_locked=True)
            )
            if record is None:
                session.rollback()
                return "skipped"
            record.delivery_attempts += 1
            record.last_attempt_at = now
            record.last_error = f"{type(error).__name__}: {error}"[:4000]
            record.claimed_at = None
            if record.delivery_attempts >= self._max_retries:
                record.status = OutboxStatus.DEAD_LETTER.value
                record.is_dead_letter = True
                outcome = "dead_lettered"
            else:
                record.status = OutboxStatus.PENDING.value
                record.available_at = now + self._retry_delay
                record.is_dead_letter = False
                outcome = "retried"
            session.commit()
        log_event(
            self._logger,
            "event_handler_failed",
            event_id=str(event_id),
            outcome=outcome,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        return outcome

    @staticmethod
    def _document(record: OutboxEventRecord) -> dict[str, Any]:
        return {
            "event_id": str(record.event_id),
            "event_type": record.event_type,
            "event_version": record.event_version,
            "aggregate_type": record.aggregate_type,
            "aggregate_id": str(record.aggregate_id),
            "aggregate_version": record.aggregate_version,
            "occurred_at": record.occurred_at.isoformat(),
            "correlation_id": str(record.correlation_id),
            "causation_id": str(record.causation_id) if record.causation_id else None,
            "actor_id": str(record.actor_id) if record.actor_id else None,
            "payload": record.payload,
            "metadata": record.metadata_document,
        }
