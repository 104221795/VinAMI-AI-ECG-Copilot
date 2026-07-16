"""Relational R4 persistence for immutable troponin evidence and laboratory provenance."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class TroponinAssayRecord(Base):
    __tablename__ = "troponin_assay_definitions"
    __table_args__ = (
        UniqueConstraint("code", "effective_version", name="uq_trop_assay_code_version"),
    )
    assay_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    analyte: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(160), nullable=False)
    platform: Mapped[str] = mapped_column(String(160), nullable=False)
    assay_version: Mapped[str] = mapped_column(String(80), nullable=False)
    canonical_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    effective_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)


class TroponinEvidenceRecord(Base):
    __tablename__ = "troponin_evidence_results"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_identity",
            "source_revision",
            name="uq_trop_source_revision",
        ),
        Index("ix_trop_case_specimen", "clinical_case_id", "specimen_collected_at"),
        Index("ix_trop_accession", "accession_number"),
        Index("ix_trop_result_assay", "assay_id"),
        Index("ix_trop_result_status", "result_status"),
    )
    result_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    clinical_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    assay_id: Mapped[UUID] = mapped_column(
        ForeignKey("troponin_assay_definitions.assay_id", ondelete="RESTRICT"),
        nullable=False,
    )
    analyte: Mapped[str] = mapped_column(String(80), nullable=False)
    original_value: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    original_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    normalized_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    conversion_status: Mapped[str] = mapped_column(String(80), nullable=False)
    conversion_version: Mapped[str] = mapped_column(String(80), nullable=False)
    specimen_type: Mapped[str] = mapped_column(String(80), nullable=False)
    specimen_collected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    resulted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    result_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_limit_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    reference_limit_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_limit_source: Mapped[str | None] = mapped_column(String(240), nullable=True)
    quality_flags: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False, default=list)
    source_system: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_result_id: Mapped[str] = mapped_column(String(240), nullable=False)
    source_identity: Mapped[str] = mapped_column(String(400), nullable=False)
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    accession_number: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    supersedes_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("troponin_evidence_results.result_id", ondelete="RESTRICT"),
        nullable=True,
    )
    amendment_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recorded_by_actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=True
    )
    recorded_by_role: Mapped[str] = mapped_column(String(80), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": record_version, "version_id_generator": False}


class LaboratoryImportJobRecord(Base):
    __tablename__ = "laboratory_import_jobs"
    __table_args__ = (
        UniqueConstraint("clinical_case_id", "idempotency_key", name="uq_lab_import_case_key"),
        Index("ix_lab_import_status", "status"),
        Index("ix_lab_import_case", "clinical_case_id"),
        Index("ix_lab_import_external", "external_reference"),
    )
    import_job_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    clinical_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    connector_id: Mapped[str] = mapped_column(String(120), nullable=False)
    external_reference: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by_actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source_message_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    resulting_result_ids: Mapped[list[str]] = mapped_column(
        JSONDocument, nullable=False, default=list
    )
    parser_name: Mapped[str] = mapped_column(String(160), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False, default=list)
    failure_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_detail_safe: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": record_version, "version_id_generator": False}


class ClinicianTroponinReviewRecord(Base):
    __tablename__ = "clinician_troponin_reviews"
    __table_args__ = (Index("ix_clinician_troponin_reviews_case", "clinical_case_id"),)
    review_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    clinical_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    referenced_result_ids: Mapped[list[str]] = mapped_column(JSONDocument, nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    review_status: Mapped[str] = mapped_column(String(80), nullable=False)
    incompatibility_acknowledged: Mapped[bool] = mapped_column(nullable=False, default=False)
    quality_limitation_acknowledged: Mapped[bool] = mapped_column(nullable=False, default=False)
    repeat_measurement_requested: Mapped[bool] = mapped_column(nullable=False, default=False)
    repeat_measurement_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    supersedes_review_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinician_troponin_reviews.review_id", ondelete="RESTRICT"), nullable=True
    )
    correction_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RepeatTroponinRequestRecord(Base):
    __tablename__ = "repeat_troponin_requests"
    __table_args__ = (Index("ix_repeat_trop_case_status", "clinical_case_id", "status"),)
    request_id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    clinical_case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )
    source_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("troponin_evidence_results.result_id", ondelete="RESTRICT"), nullable=False
    )
    requested_by_actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    acknowledged_by_actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="RESTRICT"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_result_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("troponin_evidence_results.result_id", ondelete="RESTRICT"), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    correlation_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": record_version, "version_id_generator": False}


class SQLAlchemyTroponinEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def assay_by_code(self, code: str) -> TroponinAssayRecord | None:
        return self.session.scalar(
            select(TroponinAssayRecord)
            .where(TroponinAssayRecord.code == code, TroponinAssayRecord.active.is_(True))
            .order_by(TroponinAssayRecord.effective_version.desc())
        )

    def results_for_case(self, case_id: UUID) -> list[TroponinEvidenceRecord]:
        return list(
            self.session.scalars(
                select(TroponinEvidenceRecord)
                .where(TroponinEvidenceRecord.clinical_case_id == case_id)
                .order_by(
                    TroponinEvidenceRecord.specimen_collected_at, TroponinEvidenceRecord.recorded_at
                )
            )
        )

    def effective_results(self, case_id: UUID) -> list[TroponinEvidenceRecord]:
        history = self.results_for_case(case_id)
        superseded = {
            item.supersedes_result_id for item in history if item.supersedes_result_id is not None
        }
        return [
            item
            for item in history
            if item.result_id not in superseded
            and item.result_status not in {"cancelled", "entered_in_error"}
        ]

    def source_revision(
        self, source_system: str, source_identity: str, revision: int
    ) -> TroponinEvidenceRecord | None:
        return self.session.scalar(
            select(TroponinEvidenceRecord).where(
                TroponinEvidenceRecord.source_system == source_system,
                TroponinEvidenceRecord.source_identity == source_identity,
                TroponinEvidenceRecord.source_revision == revision,
            )
        )

    def reviews(self, case_id: UUID) -> list[ClinicianTroponinReviewRecord]:
        return list(
            self.session.scalars(
                select(ClinicianTroponinReviewRecord)
                .where(ClinicianTroponinReviewRecord.clinical_case_id == case_id)
                .order_by(ClinicianTroponinReviewRecord.recorded_at)
            )
        )

    def repeat_requests(self, case_id: UUID) -> list[RepeatTroponinRequestRecord]:
        return list(
            self.session.scalars(
                select(RepeatTroponinRequestRecord)
                .where(RepeatTroponinRequestRecord.clinical_case_id == case_id)
                .order_by(RepeatTroponinRequestRecord.requested_at)
            )
        )

    def import_jobs(self, case_id: UUID) -> list[LaboratoryImportJobRecord]:
        return list(
            self.session.scalars(
                select(LaboratoryImportJobRecord)
                .where(LaboratoryImportJobRecord.clinical_case_id == case_id)
                .order_by(LaboratoryImportJobRecord.requested_at.desc())
            )
        )
