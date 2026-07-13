"""SQLAlchemy mappings for transparent reasoning evidence records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class RiskScoreRecord(Base):
    """Named score result with algorithm provenance, not hidden decision logic."""

    __tablename__ = "risk_scores"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(120), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)


class ClinicalPathwayRecord(Base):
    """Review-required demo pathway suggestion with explicit safety notice."""

    __tablename__ = "clinical_pathways"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    ruleset_version: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(String(4000), nullable=False)
    demonstration_notice: Mapped[str] = mapped_column(String(200), nullable=False)
    requires_physician_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    facts: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
