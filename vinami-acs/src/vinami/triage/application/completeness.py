"""Replaceable documentation-completeness policy without clinical inference."""

from __future__ import annotations

from dataclasses import dataclass

from vinami.triage.domain.model import ObservationState, TriageAssessment, VitalObservationSet


@dataclass(frozen=True, slots=True)
class MissingDocumentationItem:
    """One neutral documentation gap returned to clients."""

    identifier: str
    description: str


class DocumentationCompletenessPolicy:
    """Versioned research-MVP documentation requirements, not clinical guidance."""

    def __init__(
        self,
        *,
        version: str = "r2-documentation-v1",
        require_chief_complaint: bool = True,
        require_onset_documentation: bool = True,
        require_initial_vitals: bool = True,
    ) -> None:
        self.version = version
        self.require_chief_complaint = require_chief_complaint
        self.require_onset_documentation = require_onset_documentation
        self.require_initial_vitals = require_initial_vitals

    def evaluate(
        self,
        triage: TriageAssessment | None,
        latest_vitals: VitalObservationSet | None,
    ) -> tuple[MissingDocumentationItem, ...]:
        """Return descriptive gaps without deriving risk, diagnosis, or treatment."""
        missing: list[MissingDocumentationItem] = []
        if self.require_chief_complaint and (triage is None or triage.chief_complaint is None):
            missing.append(
                MissingDocumentationItem(
                    "chief_complaint_missing", "Chief complaint has not been recorded"
                )
            )
        if self.require_onset_documentation and (
            triage is None or triage.symptom_onset_state is ObservationState.NOT_ASSESSED
        ):
            missing.append(
                MissingDocumentationItem(
                    "symptom_onset_not_recorded",
                    "Symptom onset has not been recorded or explicitly marked unknown",
                )
            )
        if self.require_initial_vitals and latest_vitals is None:
            missing.append(
                MissingDocumentationItem(
                    "initial_vital_set_missing", "An initial vital observation set is not recorded"
                )
            )
        return tuple(missing)
