"""Read and write ports for R9 case history, outcomes and research exports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from vinami.audit.domain.model import Outcome


@dataclass(frozen=True, slots=True)
class Page:
    """Stable pagination result for immutable history rows."""

    items: tuple[dict[str, object], ...]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True, slots=True)
class ModelProvenance:
    """Trace one persisted model execution without treating scores as diagnoses."""

    analysis_id: UUID
    study_id: UUID
    provider_name: str
    provider_version: str
    model_name: str
    model_version: str
    model_checksum: str | None
    threshold_version: str | None
    preprocessing_version: str
    label_mapping_version: str
    executed_at: datetime | None
    input_quality: str
    input_artifact_id: UUID
    input_artifact_checksum: str
    explanation_artifact_id: UUID | None
    explanation_status: str
    synthetic: bool
    status: str
    warnings: tuple[str, ...]
    record_version: int


@dataclass(frozen=True, slots=True)
class ResearchExport:
    """Metadata and payload references for one research-use export."""

    export_id: UUID
    status: str
    schema_version: str
    requested_by: UUID
    requested_by_role: str
    requested_at: datetime
    completed_at: datetime | None
    case_ids: tuple[UUID, ...]
    filters: dict[str, object]
    row_count: int
    pseudonymization_method: str
    checksum_sha256: str
    content_json: dict[str, object]
    content_csv: str
    correlation_id: UUID
    metadata: dict[str, object]


class CaseHistoryRepository(Protocol):
    """Repository owned by Timeline/Audit/Learning read and command services."""

    def case_visible(self, case_id: UUID, visible_locations: tuple[str, ...]) -> bool:
        """Return true when the caller can see the case through location scope."""

    def timeline(
        self,
        case_id: UUID,
        page: int,
        page_size: int,
        event_type: str | None,
        correction_status: str | None,
    ) -> Page:
        """Return an immutable timeline page in stable chronological order."""

    def audit(
        self,
        case_id: UUID,
        page: int,
        page_size: int,
        action: str | None,
        outcome: str | None,
    ) -> Page:
        """Return an immutable audit page in stable chronological order."""

    def outcome_history(self, case_id: UUID) -> tuple[Outcome, ...]:
        """Return outcome revisions newest first."""

    def latest_outcome(self, case_id: UUID) -> Outcome | None:
        """Return the current effective outcome revision if present."""

    def get_outcome(self, outcome_id: UUID) -> Outcome | None:
        """Return one outcome revision by identifier."""

    def add_outcome(self, outcome: Outcome) -> None:
        """Append one outcome revision."""

    def model_provenance(self, case_id: UUID) -> tuple[ModelProvenance, ...]:
        """Return model execution provenance for ECG AI analyses."""

    def build_research_export(
        self,
        case_ids: tuple[UUID, ...],
        requested_by: UUID,
        requested_by_role: str,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> ResearchExport:
        """Create a pseudonymized research export from persisted source records."""

    def add_research_export(self, export: ResearchExport, idempotency_key: str) -> None:
        """Persist export metadata and generated payloads."""

    def get_research_export(self, export_id: UUID) -> ResearchExport | None:
        """Return one persisted research export."""

    def find_research_export(self, actor_id: UUID, idempotency_key: str) -> ResearchExport | None:
        """Return an exact export command duplicate for idempotency."""
