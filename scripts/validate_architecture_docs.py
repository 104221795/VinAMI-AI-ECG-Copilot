"""Validate the required Sprint 0 architecture documentation surface."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "docs/PROGRAM_CHARTER.md",
    "docs/architecture/system-context.md",
    "docs/architecture/container-view.md",
    "docs/architecture/component-view.md",
    "docs/architecture/bounded-contexts.md",
    "docs/architecture/domain-model.md",
    "docs/architecture/event-catalog.md",
    "docs/architecture/sequence-flows.md",
    "docs/architecture/deployment-view.md",
    "docs/architecture/dependency-rules.md",
    "docs/architecture/data-classification.md",
    "docs/adr/ADR-001-modular-monolith.md",
    "docs/adr/ADR-002-hexagonal-architecture.md",
    "docs/adr/ADR-003-event-outbox.md",
    "docs/adr/ADR-004-ai-provider-boundary.md",
    "docs/adr/ADR-005-streamlit-api-only.md",
    "docs/adr/ADR-006-clinical-safety-boundary.md",
    "docs/mvp/scope.md",
    "docs/mvp/use-cases.md",
    "docs/mvp/acceptance-criteria.md",
    "docs/mvp/non-functional-requirements.md",
    "docs/mvp/risk-register.md",
    "docs/mvp/traceability-matrix.md",
]
REQUIRED_EVENTS = [
    "PatientRegistered", "EncounterStarted", "ClinicalCaseOpened", "SymptomsRecorded",
    "VitalsRecorded", "ECGUploaded", "ECGQualityAssessed", "AIAnalysisRequested",
    "AIAnalysisCompleted", "AIAnalysisFailed", "TroponinOrdered", "TroponinCollected",
    "TroponinResulted", "RepeatECGRequested", "RepeatECGDue", "ClinicalPathwaySuggested",
    "PhysicianReviewRequested", "PhysicianDecisionRecorded", "TaskCreated", "TaskCompleted",
    "AlertRaised", "AlertAcknowledged", "CathLabReviewRequested", "TransferRequested", "CaseClosed",
]


def main() -> None:
    """Fail when the required documentation or Sprint 0 event catalog is incomplete."""
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
    if missing:
        raise SystemExit(f"Missing required architecture documents: {', '.join(missing)}")

    content = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in REQUIRED_FILES)
    missing_events = [event for event in REQUIRED_EVENTS if event not in content]
    if missing_events:
        raise SystemExit(f"Missing required event names: {', '.join(missing_events)}")

    mermaid_blocks = content.count("```mermaid")
    if mermaid_blocks < 10:
        raise SystemExit(f"Expected at least 10 Mermaid diagrams; found {mermaid_blocks}")
    print(f"ARCHITECTURE_DOCS_VALID: files={len(REQUIRED_FILES)} events={len(REQUIRED_EVENTS)} mermaid={mermaid_blocks}")


if __name__ == "__main__":
    main()

