"""Registry of event types and immutable payload-schema versions."""

from __future__ import annotations

from dataclasses import dataclass


class UnsupportedEventVersionError(ValueError):
    """Raised when a dispatcher cannot safely deserialize an event schema version."""


@dataclass(frozen=True, slots=True)
class RegisteredEvent:
    """One supported event type/version contract."""

    event_type: str
    event_version: int


class EventRegistry:
    """Own supported event contracts without coupling to a transport implementation."""

    def __init__(self) -> None:
        """Create an empty event registry for dependency injection."""
        self._events: set[RegisteredEvent] = set()

    def register(self, event_type: str, event_version: int = 1) -> None:
        """Register one immutable payload contract version."""
        if not event_type.strip():
            raise ValueError("event_type must not be blank")
        if event_version < 1:
            raise ValueError("event_version must be at least one")
        self._events.add(RegisteredEvent(event_type.strip(), event_version))

    def ensure_supported(self, event_type: str, event_version: int) -> None:
        """Reject unknown schema versions instead of silently misinterpreting payloads."""
        if RegisteredEvent(event_type, event_version) not in self._events:
            raise UnsupportedEventVersionError(
                f"unsupported event schema: {event_type}@{event_version}"
            )

    @classmethod
    def default(cls) -> EventRegistry:
        """Build the MVP registry from the approved event catalog."""
        registry = cls()
        for event_type in (
            "PatientRegistered.v1",
            "EncounterStarted.v1",
            "ClinicalCaseOpened.v1",
            "SymptomsRecorded.v1",
            "VitalsRecorded.v1",
            "ECGUploaded.v1",
            "ECGQualityAssessed.v1",
            "AIAnalysisRequested.v1",
            "AIAnalysisCompleted.v1",
            "AIAnalysisFailed.v1",
            "TroponinOrdered.v1",
            "TroponinCollected.v1",
            "TroponinResulted.v1",
            "RepeatECGRequested.v1",
            "RepeatECGDue.v1",
            "ClinicalPathwaySuggested.v1",
            "WorkflowTransitioned.v1",
            "PhysicianReviewRequested.v1",
            "PhysicianDecisionRecorded.v1",
            "TaskCreated.v1",
            "TaskCompleted.v1",
            "AlertRaised.v1",
            "AlertAcknowledged.v1",
            "AlertResolved.v1",
            "CathLabReviewRequested.v1",
            "TransferRequested.v1",
            "CaseClosed.v1",
        ):
            registry.register(event_type)
        return registry
