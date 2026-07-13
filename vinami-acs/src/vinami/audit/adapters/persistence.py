"""Append-only audit, outcome, and transactional outbox mappings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class AuditLogRecord(Base):
    """Append-only audit entry for an aggregate action or delivered event."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    aggregate_type: Mapped[str] = mapped_column(String(160), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    identity_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    actor_roles: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False, default=list)
    applied_permission: Mapped[str | None] = mapped_column(String(120), nullable=True)
    identity_provider: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authentication_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    session_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_source: Mapped[str] = mapped_column(String(160), nullable=False, default="internal")
    prior_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resulting_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False, default=dict)
    source_event_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, unique=True)


class OutcomeRecord(Base):
    """Recorded case outcome, separate from unverified clinical rules."""

    __tablename__ = "outcomes"
    __table_args__ = (UniqueConstraint("case_id", name="uq_outcome_case"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(4000), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    recorded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )


class OutboxEventRecord(Base):
    """Transactional outbox row staged alongside aggregate persistence changes."""

    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_outbox_event_id"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    aggregate_type: Mapped[str] = mapped_column(String(160), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    aggregate_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    actor_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False)
    metadata_document: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONDocument, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    is_dead_letter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EventConsumptionRecord(Base):
    """Idempotent handler completion ledger for at-least-once event delivery."""

    __tablename__ = "event_consumptions"
    __table_args__ = (
        UniqueConstraint("event_id", "handler_name", name="uq_event_consumption_handler"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("outbox_events.event_id", ondelete="CASCADE"), nullable=False, index=True
    )
    handler_name: Mapped[str] = mapped_column(String(240), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
