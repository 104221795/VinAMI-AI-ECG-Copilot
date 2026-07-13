"""Read port for the evidence required by safe clinical-case closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CaseClosureEvidence:
    """Current relational facts consulted by the demonstration closure policy."""

    unresolved_critical_alerts: int
    unresolved_consequential_tasks: int
    disposition_outcome_id: UUID | None


class CaseClosureEvidenceRepository(Protocol):
    """Query safety-owned closure evidence without exposing ORM records."""

    def for_case(self, case_id: UUID) -> CaseClosureEvidence:
        """Return current alert, task, and disposition evidence for one case."""
