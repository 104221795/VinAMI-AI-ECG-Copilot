"""SQLAlchemy persistence for R10 inbound hospital integration messages."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Index, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.integration.domain.model import IntegrationMessage
from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class IntegrationMessageRecord(Base):
    """Append-only-ish inbound message ledger with mutable processing status."""

    __tablename__ = "integration_messages"
    __table_args__ = (
        UniqueConstraint("source_system", "external_message_id", name="uq_integration_source_msg"),
        Index("ix_integration_status_received", "status", "received_at"),
        Index("ix_integration_case_received", "clinical_case_id", "received_at"),
        Index("ix_integration_correlation", "correlation_id"),
    )

    message_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    external_message_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_system: Mapped[str] = mapped_column(String(160), nullable=False)
    message_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(String(120), nullable=False)
    clinical_case_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_errors: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False, default=list)
    linked_record_ids: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False, default=list)
    payload: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False, default=dict)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dead_letter_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    simulated: Mapped[bool] = mapped_column(nullable=False, default=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": record_version, "version_id_generator": False}


class SQLAlchemyIntegrationMessageRepository:
    """Repository for inbound message idempotency, status and history queries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, record: IntegrationMessageRecord) -> None:
        self.session.add(record)

    def get(self, message_id: UUID) -> IntegrationMessageRecord | None:
        return self.session.get(IntegrationMessageRecord, message_id)

    def by_external_id(
        self, source_system: str, external_message_id: str
    ) -> IntegrationMessageRecord | None:
        return self.session.scalar(
            select(IntegrationMessageRecord).where(
                IntegrationMessageRecord.source_system == source_system,
                IntegrationMessageRecord.external_message_id == external_message_id,
            )
        )

    def latest(
        self,
        *,
        status: str | None = None,
        source_system: str | None = None,
        limit: int = 50,
    ) -> list[IntegrationMessageRecord]:
        statement = select(IntegrationMessageRecord)
        if status:
            statement = statement.where(IntegrationMessageRecord.status == status)
        if source_system:
            statement = statement.where(IntegrationMessageRecord.source_system == source_system)
        return list(
            self.session.scalars(
                statement.order_by(
                    IntegrationMessageRecord.received_at.desc(),
                    IntegrationMessageRecord.message_id.desc(),
                ).limit(limit)
            )
        )


def message_from_record(record: IntegrationMessageRecord) -> IntegrationMessage:
    """Map persistence state to the API-safe domain read model."""
    return IntegrationMessage(
        message_id=record.message_id,
        external_message_id=record.external_message_id,
        source_system=record.source_system,
        message_type=record.message_type,
        schema_version=record.schema_version,
        clinical_case_id=record.clinical_case_id,
        received_at=record.received_at,
        processed_at=record.processed_at,
        status=record.status,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        retry_count=record.retry_count,
        validation_errors=tuple(record.validation_errors),
        linked_record_ids=tuple(record.linked_record_ids),
        payload=dict(record.payload),
        dead_letter_reason=record.dead_letter_reason,
        simulated=record.simulated,
        record_version=record.record_version,
    )
