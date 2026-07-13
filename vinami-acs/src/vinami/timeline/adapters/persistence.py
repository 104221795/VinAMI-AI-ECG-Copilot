"""SQLAlchemy mapping for immutable case timeline projections."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class TimelineEventRecord(Base):
    """Chronological event projection owned by Timeline and Audit."""

    __tablename__ = "timeline_events"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False, default=dict)
    source_event_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, unique=True)
