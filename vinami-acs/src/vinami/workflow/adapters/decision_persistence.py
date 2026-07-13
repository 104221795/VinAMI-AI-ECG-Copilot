"""SQLAlchemy adapter for append-only physician decisions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint, exists, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.shared.persistence import Base, UTCDateTime, UUIDType
from vinami.workflow.domain.decision import (
    PhysicianDecision,
    PhysicianDecisionStatus,
    PhysicianDecisionType,
)


class PhysicianDecisionRecord(Base):
    """Immutable authority record; corrections are represented by another row."""

    __tablename__ = "physician_decisions"
    __table_args__ = (
        UniqueConstraint(
            "clinical_case_id",
            "correlation_id",
            "decision_type",
            name="uq_physician_decision_idempotency",
        ),
    )

    decision_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    clinical_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    decision_type: Mapped[PhysicianDecisionType] = mapped_column(
        Enum(PhysicianDecisionType, name="physician_decision_type"), nullable=False, index=True
    )
    decision_status: Mapped[PhysicianDecisionStatus] = mapped_column(
        Enum(PhysicianDecisionStatus, name="physician_decision_status"),
        nullable=False,
        index=True,
    )
    reason_code: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    evidence_snapshot_reference: Mapped[str] = mapped_column(String(2000), nullable=False)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False, index=True)
    causation_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True, index=True)
    corrects_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("physician_decisions.decision_id", ondelete="RESTRICT"), nullable=True
    )


def decision_to_record(decision: PhysicianDecision) -> PhysicianDecisionRecord:
    """Map an immutable domain decision to a new persistence record."""
    return PhysicianDecisionRecord(
        decision_id=decision.decision_id,
        clinical_case_id=decision.clinical_case_id,
        actor_id=decision.actor_id,
        actor_role=decision.actor_role,
        decision_type=decision.decision_type,
        decision_status=decision.decision_status,
        reason_code=decision.reason_code,
        note=decision.note,
        evidence_snapshot_reference=decision.evidence_snapshot_reference,
        workflow_version=decision.workflow_version,
        aggregate_expected_version=decision.aggregate_expected_version,
        occurred_at=decision.occurred_at,
        recorded_at=decision.recorded_at,
        correlation_id=decision.correlation_id,
        causation_id=decision.causation_id,
        corrects_decision_id=decision.corrects_decision_id,
    )


def decision_from_record(record: PhysicianDecisionRecord) -> PhysicianDecision:
    """Rehydrate one immutable decision without creating any event."""
    return PhysicianDecision(
        decision_id=record.decision_id,
        clinical_case_id=record.clinical_case_id,
        actor_id=record.actor_id,
        actor_role=record.actor_role,
        decision_type=record.decision_type,
        decision_status=record.decision_status,
        reason_code=record.reason_code,
        note=record.note,
        evidence_snapshot_reference=record.evidence_snapshot_reference,
        workflow_version=record.workflow_version,
        aggregate_expected_version=record.aggregate_expected_version,
        occurred_at=record.occurred_at,
        recorded_at=record.recorded_at,
        correlation_id=record.correlation_id,
        causation_id=record.causation_id,
        corrects_decision_id=record.corrects_decision_id,
    )


class SQLAlchemyPhysicianDecisionRepository:
    """Append-only physician-decision repository."""

    def __init__(self, session: Session) -> None:
        """Bind decision persistence to an explicit transaction."""
        self._session = session

    def add(self, decision: PhysicianDecision) -> None:
        """Insert and flush a decision before workflow code can consume its identifier."""
        if self._session.get(PhysicianDecisionRecord, decision.decision_id) is not None:
            raise ValueError(f"physician decision {decision.decision_id} already exists")
        self._session.add(decision_to_record(decision))
        self._session.flush()

    def get(self, decision_id: UUID) -> PhysicianDecision | None:
        """Return a decision by its immutable identifier."""
        record = self._session.get(PhysicianDecisionRecord, decision_id)
        return decision_from_record(record) if record is not None else None

    def is_effective(self, decision_id: UUID) -> bool:
        """Reject absent/revoked rows and active rows with an append-only revocation."""
        record = self._session.get(PhysicianDecisionRecord, decision_id)
        if record is None or record.decision_status is PhysicianDecisionStatus.REVOKED:
            return False
        revoked = self._session.scalar(
            select(
                exists().where(
                    PhysicianDecisionRecord.corrects_decision_id == decision_id,
                    PhysicianDecisionRecord.decision_status == PhysicianDecisionStatus.REVOKED,
                )
            )
        )
        return not bool(revoked)
