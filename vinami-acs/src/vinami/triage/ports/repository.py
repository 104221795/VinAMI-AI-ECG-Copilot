"""Persistence port for R2 clinical documentation."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vinami.triage.domain.model import TriageAssessment, VitalObservationSet


class ClinicalDocumentationRepository(Protocol):
    """Append and read triage/vital revisions through a transaction-bound port."""

    def add_triage(self, assessment: TriageAssessment) -> None: ...

    def get_triage(self, assessment_id: UUID) -> TriageAssessment | None: ...

    def current_triage(self, case_id: UUID) -> TriageAssessment | None: ...

    def triage_history(self, case_id: UUID) -> list[TriageAssessment]: ...

    def add_vital_set(self, vital_set: VitalObservationSet) -> None: ...

    def get_vital_set(self, vital_set_id: UUID) -> VitalObservationSet | None: ...

    def latest_vital_set(self, case_id: UUID) -> VitalObservationSet | None: ...

    def vital_history(self, case_id: UUID) -> list[VitalObservationSet]: ...

    def next_vital_sequence(self, case_id: UUID) -> int: ...
