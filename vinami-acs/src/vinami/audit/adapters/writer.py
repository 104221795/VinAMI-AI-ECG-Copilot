"""SQLAlchemy implementation of append-only command audit persistence."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from vinami.audit.adapters.persistence import AuditLogRecord
from vinami.audit.domain.model import AuditEntry
from vinami.timeline.adapters.persistence import TimelineEventRecord


class SQLAlchemyAuditWriter:
    """Append command outcomes in an independent, explicit transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Receive the production session factory through dependency injection."""
        self._session_factory = session_factory

    def append(self, entry: AuditEntry) -> None:
        """Idempotently append audit and timeline rows keyed by the entry identifier."""
        with self._session_factory() as session:
            if session.get(AuditLogRecord, entry.id) is not None:
                return
            session.add(
                AuditLogRecord(
                    id=entry.id,
                    case_id=entry.case_id,
                    aggregate_type=entry.aggregate_type,
                    aggregate_id=entry.aggregate_id,
                    action=entry.action,
                    actor_id=entry.actor_id,
                    actor_role=entry.actor_role,
                    prior_version=entry.prior_version,
                    resulting_version=entry.resulting_version,
                    reason=entry.reason,
                    correlation_id=entry.correlation_id,
                    causation_id=entry.causation_id,
                    outcome=entry.outcome,
                    occurred_at=entry.occurred_at,
                    payload=entry.payload,
                    source_event_id=None,
                )
            )
            if entry.case_id is not None:
                session.add(
                    TimelineEventRecord(
                        id=entry.id,
                        case_id=entry.case_id,
                        event_type=f"Command{entry.outcome.title()}",
                        occurred_at=entry.occurred_at,
                        payload={
                            "action": entry.action,
                            "actor_role": entry.actor_role,
                            "reason": entry.reason,
                            "correlation_id": str(entry.correlation_id),
                            "causation_id": (
                                str(entry.causation_id) if entry.causation_id else None
                            ),
                            "prior_version": entry.prior_version,
                            "resulting_version": entry.resulting_version,
                            "outcome": entry.outcome,
                        },
                        source_event_id=None,
                    )
                )
            session.commit()
