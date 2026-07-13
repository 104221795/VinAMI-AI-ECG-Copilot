"""SQLAlchemy mappings and repository for ECG evidence and normalized AI outputs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.ecg.domain.model import (
    ECGAcquisitionMetadata,
    ECGAIResult,
    ECGFinding,
    ECGQualityAssessment,
    ECGStudy,
)
from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType


class ECGStudyRecord(Base):
    """Immutable input reference plus quality metadata for one ECG study."""

    __tablename__ = "ecg_studies"
    __table_args__ = (UniqueConstraint("input_reference", name="uq_ecg_study_input_reference"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    input_reference: Mapped[str] = mapped_column(String(2000), nullable=False)
    content_checksum: Mapped[str | None] = mapped_column(String(256), nullable=True)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    acquisition_metadata: Mapped[dict[str, object]] = mapped_column(JSONDocument, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    quality: Mapped[ECGQualityAssessment] = mapped_column(
        Enum(ECGQualityAssessment, name="ecg_quality_assessment"), nullable=False
    )
    quality_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class ECGAIResultRecord(Base):
    """Provider-neutral AI evidence record linked to one ECG study."""

    __tablename__ = "ecg_ai_results"
    __table_args__ = (UniqueConstraint("study_id", name="uq_ecg_ai_result_study"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    study_id: Mapped[UUID] = mapped_column(
        ForeignKey("ecg_studies.id", ondelete="CASCADE"), nullable=False
    )
    model_registry_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_registry.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(200), nullable=False)
    input_reference: Mapped[str] = mapped_column(String(2000), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    limitations: Mapped[str] = mapped_column(String(4000), nullable=False)
    explanation_reference: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class ECGFindingRecord(Base):
    """Relational normalized output label for an AI evidence record."""

    __tablename__ = "ecg_findings"
    __table_args__ = (
        UniqueConstraint("ai_result_id", "label", name="uq_ecg_finding_result_label"),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    ai_result_id: Mapped[UUID] = mapped_column(
        ForeignKey("ecg_ai_results.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)


def _metadata_to_document(metadata: ECGAcquisitionMetadata) -> dict[str, object]:
    return {
        "device_name": metadata.device_name,
        "sampling_hz": metadata.sampling_hz,
        "lead_count": metadata.lead_count,
        "acquired_at": metadata.acquired_at.isoformat() if metadata.acquired_at else None,
        "source_system": metadata.source_system,
        "source_record_id": metadata.source_record_id,
        "device_vendor": metadata.device_vendor,
        "input_format": metadata.input_format,
        "lead_configuration": metadata.lead_configuration,
    }


def _metadata_from_document(document: dict[str, object]) -> ECGAcquisitionMetadata:
    device_name = document.get("device_name")
    sampling_hz = document.get("sampling_hz")
    lead_count = document.get("lead_count")
    acquired_at = document.get("acquired_at")
    source_system = document.get("source_system")
    source_record_id = document.get("source_record_id")
    device_vendor = document.get("device_vendor")
    input_format = document.get("input_format")
    lead_configuration = document.get("lead_configuration")
    return ECGAcquisitionMetadata(
        device_name=device_name if isinstance(device_name, str) else None,
        sampling_hz=sampling_hz if isinstance(sampling_hz, int) else None,
        lead_count=lead_count if isinstance(lead_count, int) else None,
        acquired_at=datetime.fromisoformat(acquired_at) if isinstance(acquired_at, str) else None,
        source_system=source_system if isinstance(source_system, str) else "unspecified",
        source_record_id=source_record_id if isinstance(source_record_id, str) else None,
        device_vendor=device_vendor if isinstance(device_vendor, str) else None,
        input_format=input_format if isinstance(input_format, str) else None,
        lead_configuration=(lead_configuration if isinstance(lead_configuration, str) else None),
    )


class SQLAlchemyECGStudyRepository:
    """ECG repository with relational findings rather than an opaque prediction blob."""

    def __init__(self, session: Session) -> None:
        """Bind the repository to an explicit unit-of-work session."""
        self._session = session

    def add(self, study: ECGStudy) -> None:
        """Insert an ECG study and optional normalized result/finding rows."""
        if self._session.get(ECGStudyRecord, study.id) is not None:
            raise ValueError(f"ECG study {study.id} already exists")
        record = ECGStudyRecord(
            id=study.id,
            case_id=study.case_id,
            input_reference=study.input_reference,
            content_checksum=study.content_checksum,
            media_type=study.media_type,
            acquisition_metadata=_metadata_to_document(study.metadata),
            uploaded_at=study.uploaded_at,
            quality=study.quality,
            quality_note=study.quality_note,
        )
        self._session.add(record)
        self._replace_ai_result(study)

    def get(self, study_id: UUID) -> ECGStudy | None:
        """Rehydrate an ECG study and its optional normalized result."""
        record = self._session.get(ECGStudyRecord, study_id)
        if record is None:
            return None
        result_record = (
            self._session.query(ECGAIResultRecord).filter_by(study_id=study_id).one_or_none()
        )
        result = None
        if result_record is not None:
            findings = tuple(
                ECGFinding(item.label, item.score, item.threshold)
                for item in self._session.query(ECGFindingRecord)
                .filter_by(ai_result_id=result_record.id)
                .order_by(ECGFindingRecord.label)
            )
            result = ECGAIResult(
                model_name=result_record.model_name,
                model_version=result_record.model_version,
                input_reference=result_record.input_reference,
                analyzed_at=result_record.analyzed_at,
                findings=findings,
                limitations=result_record.limitations,
                explanation_reference=result_record.explanation_reference,
                provider_name=result_record.provider_name,
            )
        return ECGStudy(
            id=record.id,
            case_id=record.case_id,
            input_reference=record.input_reference,
            content_checksum=record.content_checksum,
            media_type=record.media_type,
            metadata=_metadata_from_document(record.acquisition_metadata),
            uploaded_at=record.uploaded_at,
            quality=record.quality,
            quality_note=record.quality_note,
            ai_result=result,
        )

    def save(self, study: ECGStudy) -> None:
        """Persist quality and replace the one normalized AI result when present."""
        record = self._session.get(ECGStudyRecord, study.id)
        if record is None:
            raise ValueError(f"ECG study {study.id} does not exist")
        record.quality = study.quality
        record.quality_note = study.quality_note
        self._replace_ai_result(study)

    def _replace_ai_result(self, study: ECGStudy) -> None:
        if study.ai_result is None:
            return
        existing = self._session.query(ECGAIResultRecord).filter_by(study_id=study.id).one_or_none()
        if existing is not None:
            self._session.query(ECGFindingRecord).filter_by(ai_result_id=existing.id).delete()
            self._session.delete(existing)
            self._session.flush()
        result = study.ai_result
        result_record = ECGAIResultRecord(
            study_id=study.id,
            model_name=result.model_name,
            model_version=result.model_version,
            provider_name=result.provider_name,
            input_reference=result.input_reference,
            analyzed_at=result.analyzed_at,
            limitations=result.limitations,
            explanation_reference=result.explanation_reference,
        )
        self._session.add(result_record)
        self._session.flush()
        self._session.add_all(
            [
                ECGFindingRecord(
                    ai_result_id=result_record.id,
                    label=finding.label,
                    score=finding.score,
                    threshold=finding.threshold,
                )
                for finding in result.findings
            ]
        )
