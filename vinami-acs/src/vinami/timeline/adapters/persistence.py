"""SQLAlchemy mapping for immutable case timeline projections."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class TimelineEventRecord(Base):
    """Chronological event projection owned by Timeline and Audit."""

    __tablename__ = "timeline_events"
    __table_args__ = (
        UniqueConstraint("case_id", "source_event_id", name="uq_timeline_case_source_event"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False, default=dict)
    source_event_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    source_record_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    source_record_version: Mapped[int | None] = mapped_column(nullable=True)
    correction_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="original", index=True
    )
    supersedes_timeline_event_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    revokes_timeline_event_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    data_classification: Mapped[str] = mapped_column(String(80), nullable=False, default="clinical")
