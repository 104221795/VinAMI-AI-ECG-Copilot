"""SQLAlchemy mappings for recorded triage facts owned by the Triage context."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from vinami.shared.persistence import Base, UTCDateTime, UUIDType


class SymptomObservationRecord(Base):
    """Append-only symptom observation associated with one clinical case."""

    __tablename__ = "symptom_observations"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)


class VitalObservationRecord(Base):
    """Append-only numeric vital observation associated with one clinical case."""

    __tablename__ = "vital_observations"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
