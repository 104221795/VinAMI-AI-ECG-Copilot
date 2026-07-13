"""SQLAlchemy mapping and repository for the ClinicalCase aggregate."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.clinical_case.domain.model import CaseStatus, ClinicalCase, ClinicalPriority
from vinami.clinical_case.ports.repository import ClinicalCaseListRecord
from vinami.patient.adapters.persistence import EncounterRecord
from vinami.shared.persistence import Base, UTCDateTime, UUIDType


class ClinicalCaseRecord(Base):
    """System-of-record mapping for one suspected ACS case lifecycle."""

    __tablename__ = "clinical_cases"
    __table_args__ = (
        UniqueConstraint("closure_command_id", name="uq_clinical_case_closure_command"),
        Index(
            "uq_clinical_cases_active_encounter",
            "encounter_id",
            unique=True,
            postgresql_where=text("status IN ('OPEN', 'UNDER_REVIEW')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("encounters.id", ondelete="RESTRICT"), index=True
    )
    opening_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    priority: Mapped[ClinicalPriority] = mapped_column(
        Enum(ClinicalPriority, name="clinical_priority"), nullable=False, index=True
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status"), nullable=False, index=True
    )
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    closed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=True
    )
    closure_actor_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    closure_command_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    closure_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "physician_decisions.decision_id",
            name="fk_clinical_cases_closure_decision",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
    )
    disposition_outcome_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "outcomes.id",
            name="fk_clinical_cases_disposition_outcome",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}


def case_to_record(case: ClinicalCase) -> ClinicalCaseRecord:
    """Map a newly opened aggregate into a persistence record."""
    return ClinicalCaseRecord(
        id=case.id,
        encounter_id=case.encounter_id,
        opening_reason=case.opening_reason,
        priority=case.priority,
        status=case.status,
        opened_at=case.opened_at,
        updated_at=case.updated_at or case.opened_at,
        closed_at=case.closed_at,
        closure_reason=case.closure_reason,
        closed_by=case.closed_by,
        closure_actor_role=case.closure_actor_role,
        closure_command_id=case.closure_command_id,
        closure_decision_id=case.closure_decision_id,
        disposition_outcome_id=case.disposition_outcome_id,
        version=case.version,
    )


def case_from_record(record: ClinicalCaseRecord) -> ClinicalCase:
    """Rehydrate a case without replaying lifecycle events."""
    return ClinicalCase(
        id=record.id,
        encounter_id=record.encounter_id,
        opening_reason=record.opening_reason,
        priority=record.priority,
        status=record.status,
        opened_at=record.opened_at,
        updated_at=record.updated_at,
        version=record.version,
        closed_at=record.closed_at,
        closure_reason=record.closure_reason,
        closed_by=record.closed_by,
        closure_actor_role=record.closure_actor_role,
        closure_command_id=record.closure_command_id,
        closure_decision_id=record.closure_decision_id,
        disposition_outcome_id=record.disposition_outcome_id,
    )


class SQLAlchemyClinicalCaseRepository:
    """Case repository that relies on SQLAlchemy version predicates during flush."""

    def __init__(self, session: Session) -> None:
        """Bind repository work to the unit-of-work session."""
        self._session = session

    def add(self, case: ClinicalCase) -> None:
        """Insert a newly opened case."""
        if self._session.get(ClinicalCaseRecord, case.id) is not None:
            raise ValueError(f"clinical case {case.id} already exists")
        self._session.add(case_to_record(case))

    def get(self, case_id: UUID) -> ClinicalCase | None:
        """Retrieve one case aggregate by UUID."""
        record = self._session.get(ClinicalCaseRecord, case_id)
        return case_from_record(record) if record is not None else None

    def save(self, case: ClinicalCase) -> None:
        """Apply an aggregate lifecycle transition to its tracked persistence record."""
        record = self._session.get(ClinicalCaseRecord, case.id)
        if record is None:
            raise ValueError(f"clinical case {case.id} does not exist")
        record.priority = case.priority
        record.status = case.status
        record.updated_at = case.updated_at or case.opened_at
        record.closed_at = case.closed_at
        record.closure_reason = case.closure_reason
        record.closed_by = case.closed_by
        record.closure_actor_role = case.closure_actor_role
        record.closure_command_id = case.closure_command_id
        record.closure_decision_id = case.closure_decision_id
        record.disposition_outcome_id = case.disposition_outcome_id
        record.version = case.version

    def get_active_for_encounter(self, encounter_id: UUID) -> ClinicalCase | None:
        """Return the single non-closed case allowed for an encounter."""
        record = self._session.scalar(
            select(ClinicalCaseRecord).where(
                ClinicalCaseRecord.encounter_id == encounter_id,
                ClinicalCaseRecord.status.in_((CaseStatus.OPEN, CaseStatus.UNDER_REVIEW)),
            )
        )
        return case_from_record(record) if record is not None else None

    def list_active(
        self,
        *,
        offset: int,
        limit: int,
        status: str | None,
        priority: str | None,
        location: str | None,
    ) -> tuple[list[ClinicalCaseListRecord], int]:
        """Read an explicitly ordered active-case page with parent encounter location."""
        filters = [ClinicalCaseRecord.status != CaseStatus.CLOSED]
        if status is not None:
            filters.append(ClinicalCaseRecord.status == CaseStatus(status))
        if priority is not None:
            filters.append(ClinicalCaseRecord.priority == ClinicalPriority(priority))
        if location is not None:
            filters.append(EncounterRecord.location == location)
        base = (
            select(ClinicalCaseRecord, EncounterRecord.location)
            .join(EncounterRecord, EncounterRecord.id == ClinicalCaseRecord.encounter_id)
            .where(*filters)
        )
        total = (
            self._session.scalar(select(func.count()).select_from(base.order_by(None).subquery()))
            or 0
        )
        rows = self._session.execute(
            base.order_by(ClinicalCaseRecord.updated_at.desc(), ClinicalCaseRecord.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return (
            [ClinicalCaseListRecord(case_from_record(row[0]), str(row[1])) for row in rows],
            total,
        )
