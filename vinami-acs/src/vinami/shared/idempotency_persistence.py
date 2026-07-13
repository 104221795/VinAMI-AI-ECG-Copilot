"""SQLAlchemy adapter for transaction-scoped command idempotency."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.shared.idempotency import IdempotencyResult
from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class CommandIdempotencyRecord(Base):
    """Durable successful command result keyed by actor, command type, and caller key."""

    __tablename__ = "command_idempotency"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "command_type", "idempotency_key", name="uq_command_idempotency_scope"
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    command_type: Mapped[str] = mapped_column(String(120), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    command_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, unique=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)


class SQLAlchemyIdempotencyRepository:
    """Persist command results while serializing concurrent requests for the same scope."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an explicit unit-of-work transaction."""
        self._session = session

    def lock_and_get(
        self, actor_id: UUID, command_type: str, idempotency_key: str
    ) -> IdempotencyResult | None:
        """Acquire a transaction lock and return the existing result when present."""
        lock_key = f"{actor_id}:{command_type}:{idempotency_key}"
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            self._session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                {"scope": lock_key},
            )
        record = self._session.scalar(
            select(CommandIdempotencyRecord).where(
                CommandIdempotencyRecord.actor_id == actor_id,
                CommandIdempotencyRecord.command_type == command_type,
                CommandIdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        return _from_record(record) if record is not None else None

    def add(self, result: IdempotencyResult) -> None:
        """Stage one successful result for commit with aggregate state and outbox."""
        self._session.add(
            CommandIdempotencyRecord(
                actor_id=result.actor_id,
                command_type=result.command_type,
                idempotency_key=result.idempotency_key,
                command_id=result.command_id,
                request_hash=result.request_hash,
                resource_type=result.resource_type,
                resource_id=result.resource_id,
                response_payload=result.response_payload,
                created_at=result.created_at,
            )
        )


def _from_record(record: CommandIdempotencyRecord) -> IdempotencyResult:
    return IdempotencyResult(
        actor_id=record.actor_id,
        command_type=record.command_type,
        idempotency_key=record.idempotency_key,
        command_id=record.command_id,
        request_hash=record.request_hash,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        response_payload=dict(record.response_payload),
        created_at=record.created_at,
    )
