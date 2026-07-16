"""Immutable clinical-evidence and physician-authored R5 records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID

from vinami.shared.actor import PHYSICIAN_ROLES
from vinami.shared.domain import DomainInvariantError, require_text, require_utc


class EvidenceFreshness(StrEnum):
    """Technical currency of persisted evidence at snapshot creation."""

    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"


class ClinicalDecisionType(StrEnum):
    """Documented physician plans supported by the R5 workspace."""

    CONTINUE_OBSERVATION = "continue_observation"
    REQUEST_REPEAT_ECG = "request_repeat_ecg"
    REQUEST_REPEAT_TROPONIN = "request_repeat_troponin"
    REQUEST_ADDITIONAL_INFORMATION = "request_additional_information"
    REQUEST_CARDIOLOGY_REVIEW = "request_cardiology_review"
    REQUEST_CATH_LAB_REVIEW = "request_cath_lab_review"
    MAINTAIN_CURRENT_PLAN = "maintain_current_plan"
    OTHER_DOCUMENTED_PLAN = "other_documented_plan"


class DecisionRecordStatus(StrEnum):
    """Append-only decision lifecycle; prior rows are never mutated."""

    ACTIVE = "active"
    CORRECTION = "correction"
    REVOCATION = "revocation"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """Versioned reference to a persisted source record without copying raw payloads."""

    source_type: str
    source_id: UUID
    source_version: int
    relevant_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_type", require_text(self.source_type, "source_type"))
        if self.source_version < 1:
            raise DomainInvariantError("evidence source version must be at least one")
        object.__setattr__(self, "relevant_at", require_utc(self.relevant_at, "relevant_at"))


@dataclass(frozen=True, slots=True)
class ClinicalEvidenceSnapshot:
    """Immutable synthesis of persisted facts for one clinical case."""

    snapshot_id: UUID
    clinical_case_id: UUID
    case_version: int
    record_version: int
    created_at: datetime
    created_by_actor_id: UUID
    sources: tuple[EvidenceReference, ...]
    summaries: Mapping[str, Any]
    freshness: Mapping[str, EvidenceFreshness]
    missing_evidence: tuple[str, ...]
    technical_conflicts: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.case_version < 1 or self.record_version < 1:
            raise DomainInvariantError("snapshot versions must be at least one")
        object.__setattr__(self, "created_at", require_utc(self.created_at, "created_at"))
        object.__setattr__(self, "summaries", MappingProxyType(dict(self.summaries)))
        object.__setattr__(self, "freshness", MappingProxyType(dict(self.freshness)))


@dataclass(frozen=True, slots=True)
class PhysicianClinicalAssessment:
    """Immutable physician-authored interpretation of a specific evidence snapshot."""

    assessment_id: UUID
    clinical_case_id: UUID
    snapshot_id: UUID
    revision_number: int
    record_version: int
    summary: str
    supporting_evidence: tuple[str, ...]
    contradictory_evidence: tuple[str, ...]
    uncertainty: str
    additional_information_required: str | None
    actor_id: UUID
    actor_role: str
    recorded_at: datetime
    corrects_assessment_id: UUID | None = None
    correction_reason: str | None = None

    def __post_init__(self) -> None:
        if self.actor_role not in PHYSICIAN_ROLES:
            raise DomainInvariantError("clinical assessment requires an authorized physician")
        if self.revision_number < 1 or self.record_version < 1:
            raise DomainInvariantError("assessment versions must be at least one")
        object.__setattr__(self, "summary", require_text(self.summary, "assessment summary"))
        object.__setattr__(self, "uncertainty", require_text(self.uncertainty, "uncertainty"))
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))
        if (self.corrects_assessment_id is None) != (self.correction_reason is None):
            raise DomainInvariantError("assessment correction requires source and reason together")


@dataclass(frozen=True, slots=True)
class PhysicianDecision:
    """Immutable physician plan bound to one current snapshot and assessment."""

    decision_id: UUID
    clinical_case_id: UUID
    snapshot_id: UUID
    assessment_id: UUID
    decision_type: ClinicalDecisionType
    status: DecisionRecordStatus
    revision_number: int
    record_version: int
    rationale: str
    uncertainty: str
    evidence_references: tuple[str, ...]
    actor_id: UUID
    actor_role: str
    recorded_at: datetime
    corrects_decision_id: UUID | None = None
    correction_reason: str | None = None
    workflow_authorization_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.actor_role not in PHYSICIAN_ROLES:
            raise DomainInvariantError("clinical decision requires an authorized physician")
        if self.revision_number < 1 or self.record_version < 1:
            raise DomainInvariantError("decision versions must be at least one")
        object.__setattr__(self, "rationale", require_text(self.rationale, "decision rationale"))
        object.__setattr__(self, "uncertainty", require_text(self.uncertainty, "uncertainty"))
        object.__setattr__(self, "recorded_at", require_utc(self.recorded_at, "recorded_at"))
        if self.status is DecisionRecordStatus.ACTIVE and self.corrects_decision_id is not None:
            raise DomainInvariantError("an active decision cannot correct an earlier record")
        if self.status is not DecisionRecordStatus.ACTIVE and (
            self.corrects_decision_id is None or self.correction_reason is None
        ):
            raise DomainInvariantError("correction or revocation requires source and reason")
        if (
            self.decision_type is ClinicalDecisionType.REQUEST_CATH_LAB_REVIEW
            and self.status is not DecisionRecordStatus.REVOCATION
            and self.workflow_authorization_id is None
        ):
            raise DomainInvariantError("cath-lab review request requires workflow authorization")
