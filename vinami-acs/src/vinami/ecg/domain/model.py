"""ECG evidence aggregate and normalized AI result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from vinami.shared.domain import (
    AggregateRoot,
    DomainInvariantError,
    require_text,
    require_utc,
    utc_now,
)


class ECGQualityAssessment(StrEnum):
    """Declared quality state of an ECG input; it is not a clinical conclusion."""

    UNASSESSED = "unassessed"
    ACCEPTABLE = "acceptable"
    LIMITED = "limited"
    UNUSABLE = "unusable"


@dataclass(frozen=True, slots=True)
class ECGAcquisitionMetadata:
    """Acquisition facts required to preserve interpretation provenance."""

    device_name: str | None
    sampling_hz: int | None
    lead_count: int | None
    acquired_at: datetime | None
    source_system: str = "unspecified"
    source_record_id: str | None = None
    device_vendor: str | None = None
    input_format: str | None = None
    lead_configuration: str | None = None

    def __post_init__(self) -> None:
        """Validate positive signal metadata when known."""
        if self.sampling_hz is not None and self.sampling_hz <= 0:
            raise DomainInvariantError("sampling_hz must be positive")
        if self.lead_count is not None and self.lead_count <= 0:
            raise DomainInvariantError("lead_count must be positive")
        if self.acquired_at is not None:
            object.__setattr__(self, "acquired_at", require_utc(self.acquired_at, "acquired_at"))
        object.__setattr__(self, "source_system", require_text(self.source_system, "source_system"))
        for field_name in (
            "source_record_id",
            "device_vendor",
            "input_format",
            "lead_configuration",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_text(value, field_name))


@dataclass(frozen=True, slots=True)
class ECGFinding:
    """Normalized model output label and score, never a confirmed diagnosis."""

    label: str
    score: float
    threshold: float | None = None

    def __post_init__(self) -> None:
        """Constrain probability-like scores to a transparent range."""
        object.__setattr__(self, "label", require_text(self.label, "ECG finding label"))
        if not 0.0 <= self.score <= 1.0:
            raise DomainInvariantError("ECG finding score must be between 0 and 1")
        if self.threshold is not None and not 0.0 <= self.threshold <= 1.0:
            raise DomainInvariantError("ECG finding threshold must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class ECGAIResult:
    """Provider-neutral evidence record with mandatory model and input provenance."""

    model_name: str
    model_version: str
    input_reference: str
    analyzed_at: datetime
    findings: tuple[ECGFinding, ...]
    limitations: str
    explanation_reference: str | None = None
    provider_name: str = "unspecified"

    def __post_init__(self) -> None:
        """Enforce provenance and prevent empty normalized result records."""
        object.__setattr__(self, "model_name", require_text(self.model_name, "model_name"))
        object.__setattr__(self, "model_version", require_text(self.model_version, "model_version"))
        object.__setattr__(
            self, "input_reference", require_text(self.input_reference, "input_reference")
        )
        object.__setattr__(self, "limitations", require_text(self.limitations, "limitations"))
        object.__setattr__(self, "provider_name", require_text(self.provider_name, "provider_name"))
        object.__setattr__(self, "analyzed_at", require_utc(self.analyzed_at, "analyzed_at"))
        if not self.findings:
            raise DomainInvariantError("ECG AI result must contain at least one finding")


@dataclass(slots=True)
class ECGStudy(AggregateRoot):
    """Aggregate owning immutable ECG evidence reference and quality state."""

    case_id: UUID
    input_reference: str
    content_checksum: str | None
    media_type: str
    metadata: ECGAcquisitionMetadata
    uploaded_at: datetime
    quality: ECGQualityAssessment = ECGQualityAssessment.UNASSESSED
    quality_note: str | None = None
    ai_result: ECGAIResult | None = None

    @classmethod
    def upload(
        cls,
        case_id: UUID,
        input_reference: str,
        media_type: str,
        metadata: ECGAcquisitionMetadata,
        uploaded_at: datetime | None = None,
        study_id: UUID | None = None,
        content_checksum: str | None = None,
    ) -> ECGStudy:
        """Register immutable ECG evidence, without running a model."""
        study = cls(
            id=study_id or uuid4(),
            case_id=case_id,
            input_reference=require_text(input_reference, "input_reference"),
            content_checksum=content_checksum,
            media_type=require_text(media_type, "media_type"),
            metadata=metadata,
            uploaded_at=require_utc(uploaded_at or utc_now(), "uploaded_at"),
        )
        study._record_event(
            "ECGUploaded.v1",
            1,
            {
                "case_id": str(case_id),
                "study_id": str(study.id),
                "input_reference": study.input_reference,
            },
        )
        return study

    def assess_quality(
        self, assessment: ECGQualityAssessment, note: str, assessor_id: UUID
    ) -> None:
        """Record declared input quality with a human assessor provenance."""
        if assessment is ECGQualityAssessment.UNASSESSED:
            raise DomainInvariantError("quality assessment must be final")
        self.quality = assessment
        self.quality_note = require_text(note, "quality note")
        self._record_event(
            "ECGQualityAssessed.v1",
            1,
            {
                "study_id": str(self.id),
                "assessment": assessment.value,
                "assessor_id": str(assessor_id),
            },
        )

    def record_ai_result(self, result: ECGAIResult) -> None:
        """Persist normalized evidence only when it refers to this immutable input."""
        if result.input_reference != self.input_reference:
            raise DomainInvariantError("AI result input reference does not match ECG study")
        self.ai_result = result
        self._record_event(
            "AIAnalysisCompleted.v1",
            1,
            {
                "study_id": str(self.id),
                "model_name": result.model_name,
                "model_version": result.model_version,
            },
        )
