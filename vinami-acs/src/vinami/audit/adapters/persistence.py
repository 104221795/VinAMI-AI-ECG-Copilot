"""Append-only audit, outcome, and transactional outbox mappings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    authorization_result: Mapped[str | None] = mapped_column(String(80), nullable=True)
    correction_status: Mapped[str] = mapped_column(String(40), nullable=False, default="original")
    source_record_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OutcomeRecord(Base):
    """Append-only case outcome revision, separate from unverified clinical rules."""

    __tablename__ = "outcomes"
    __table_args__ = (
        UniqueConstraint("case_id", "revision_number", name="uq_outcome_case_revision"),
        Index("ix_outcomes_case_revision", "case_id", "revision_number"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(String(4000), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    recorded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    outcome_type: Mapped[str] = mapped_column(String(80), nullable=False, default="disposition")
    outcome_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(240), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(240), nullable=True)
    final_conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    cath_lab_review_outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    intervention_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    complications: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_completeness: Mapped[str] = mapped_column(String(80), nullable=False, default="documented")
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="physician_documented")
    actor_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    uncertainty: Mapped[str | None] = mapped_column(Text, nullable=True)
    unavailable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_outcome_id: Mapped[UUID | None] = mapped_column(
        UUIDType, ForeignKey("outcomes.id", ondelete="RESTRICT"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    correlation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)


class ResearchExportRecord(Base):
    """Research-use export package metadata and generated payload checksums."""

    __tablename__ = "clinical_research_exports"
    __table_args__ = (
        UniqueConstraint("requested_by", "idempotency_key", name="uq_research_export_actor_key"),
        Index("ix_research_exports_requested", "requested_at"),
    )

    export_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_by: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_role: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    case_ids: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    filters: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pseudonymization_method: Mapped[str] = mapped_column(String(160), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_json: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False)
    content_csv: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    metadata_document: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONDocument, nullable=False, default=dict
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
