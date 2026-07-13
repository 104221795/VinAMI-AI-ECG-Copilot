"""Typed, framework-free definitions for the versioned ACS demonstration workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from vinami.shared.domain import DomainInvariantError, require_text, require_utc, utc_now

DEMONSTRATION_NOTICE = "Demonstration workflow — not for clinical use."

AUTHORITATIVE_FACT_KEYS = frozenset(
    {
        "physician_decision_recorded",
        "pathway_approved",
        "cath_lab_review_requested",
        "case_closure_approved",
    }
)

CONSEQUENTIAL_COMMAND_TYPES = frozenset(
    {
        "record_physician_decision",
        "request_transfer",
        "request_cath_lab_review",
        "prepare_discharge_review",
        "close_case",
    }
)


class WorkflowState(StrEnum):
    """Explicit lifecycle states for a suspected ACS case workflow."""

    NEW = "NEW"
    TRIAGE_IN_PROGRESS = "TRIAGE_IN_PROGRESS"
    AWAITING_ECG = "AWAITING_ECG"
    ECG_UNDER_REVIEW = "ECG_UNDER_REVIEW"
    AWAITING_TROPONIN = "AWAITING_TROPONIN"
    OBSERVATION = "OBSERVATION"
    PHYSICIAN_REVIEW_REQUIRED = "PHYSICIAN_REVIEW_REQUIRED"
    PATHWAY_SELECTED = "PATHWAY_SELECTED"
    TRANSFER_IN_PROGRESS = "TRANSFER_IN_PROGRESS"
    CATH_LAB_REVIEW = "CATH_LAB_REVIEW"
    DISCHARGE_REVIEW = "DISCHARGE_REVIEW"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class DueTimerStatus(StrEnum):
    """Durable lifecycle of a workflow-owned due timer."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class WorkflowFacts:
    """Explicit, non-diagnostic facts consumed by transition guards."""

    ecg_available: bool = False
    ecg_quality_acceptable: bool = False
    ai_interpretation_ready: bool = False
    troponin_available: bool = False
    troponin_rising: bool = False
    conflicting_signals: bool = False
    missing_troponin_after_due: bool = False
    repeat_ecg_overdue: bool = False
    unresolved_critical_alerts: int = 0

    def __post_init__(self) -> None:
        """Reject an invalid negative critical-alert count."""
        if self.unresolved_critical_alerts < 0:
            raise DomainInvariantError("unresolved_critical_alerts cannot be negative")

    def apply_patch(self, patch: Mapping[str, Any]) -> WorkflowFacts:
        """Apply only known, typed fact updates supplied with a command."""
        privileged = set(patch).intersection(AUTHORITATIVE_FACT_KEYS)
        if privileged:
            raise DomainInvariantError(
                f"authoritative workflow state cannot be patched: {sorted(privileged)}"
            )
        allowed = set(self.__dataclass_fields__)
        unknown = set(patch).difference(allowed)
        if unknown:
            raise DomainInvariantError(f"unknown workflow facts: {sorted(unknown)}")
        return replace(self, **dict(patch))

    def as_document(self) -> dict[str, object]:
        """Return a relational-adapter-safe representation."""
        return {
            "ecg_available": self.ecg_available,
            "ecg_quality_acceptable": self.ecg_quality_acceptable,
            "ai_interpretation_ready": self.ai_interpretation_ready,
            "troponin_available": self.troponin_available,
            "troponin_rising": self.troponin_rising,
            "conflicting_signals": self.conflicting_signals,
            "missing_troponin_after_due": self.missing_troponin_after_due,
            "repeat_ecg_overdue": self.repeat_ecg_overdue,
            "unresolved_critical_alerts": self.unresolved_critical_alerts,
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any] | None) -> WorkflowFacts:
        """Rehydrate facts while rejecting unknown persistence fields."""
        return cls().apply_patch(document or {})


@dataclass(frozen=True, slots=True)
class WorkflowCommand:
    """An idempotent request to apply one named workflow transition."""

    command_type: str
    expected_version: int
    facts_patch: Mapping[str, Any] = field(default_factory=dict)
    actor_id: UUID | None = None
    actor_role: str | None = None
    decision_id: UUID | None = None
    case_expected_version: int | None = None
    correlation_id: UUID = field(default_factory=uuid4)
    causation_id: UUID | None = None
    issued_at: datetime = field(default_factory=utc_now)
    command_id: UUID = field(default_factory=uuid4)
    due_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate command identity, version, time, and optional timer due time."""
        object.__setattr__(self, "command_type", require_text(self.command_type, "command_type"))
        if self.expected_version < 1:
            raise DomainInvariantError("expected_version must be at least one")
        object.__setattr__(self, "issued_at", require_utc(self.issued_at, "issued_at"))
        if self.due_at is not None:
            object.__setattr__(self, "due_at", require_utc(self.due_at, "due_at"))
        object.__setattr__(self, "facts_patch", dict(self.facts_patch))
        privileged = set(self.facts_patch).intersection(AUTHORITATIVE_FACT_KEYS)
        if privileged:
            raise DomainInvariantError(
                f"authoritative workflow state cannot be patched: {sorted(privileged)}"
            )
        if self.command_type in CONSEQUENTIAL_COMMAND_TYPES:
            if self.actor_id is None or self.actor_role is None or self.decision_id is None:
                raise DomainInvariantError(
                    f"{self.command_type} requires actor context and a persisted decision_id"
                )
            object.__setattr__(self, "actor_role", require_text(self.actor_role, "actor_role"))
            if self.case_expected_version is None or self.case_expected_version < 1:
                raise DomainInvariantError(
                    f"{self.command_type} requires a positive case_expected_version"
                )


@dataclass(frozen=True, slots=True)
class Transition:
    """One declarative state change selected by command and satisfied guards."""

    name: str
    command_type: str
    from_state: WorkflowState
    to_state: WorkflowState
    guards: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject unnamed transition elements before a workflow is activated."""
        object.__setattr__(self, "name", require_text(self.name, "transition name"))
        object.__setattr__(self, "command_type", require_text(self.command_type, "command_type"))


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """Versioned, explicitly non-clinical workflow configuration."""

    definition_id: str
    version: str
    notice: str
    transitions: tuple[Transition, ...]

    def __post_init__(self) -> None:
        """Require the mandatory safety notice and a non-empty state graph."""
        object.__setattr__(self, "definition_id", require_text(self.definition_id, "definition_id"))
        object.__setattr__(self, "version", require_text(self.version, "definition version"))
        if self.notice != DEMONSTRATION_NOTICE:
            raise DomainInvariantError("workflow definition must carry the demonstration notice")
        if not self.transitions:
            raise DomainInvariantError("workflow definition needs at least one transition")
        names = [transition.name for transition in self.transitions]
        if len(names) != len(set(names)):
            raise DomainInvariantError("workflow transition names must be unique")


@dataclass(frozen=True, slots=True)
class WorkflowTransitionHistory:
    """Append-only provenance for one accepted command and its state transition."""

    id: UUID
    command_id: UUID
    transition_name: str
    from_state: WorkflowState
    to_state: WorkflowState
    actor_id: UUID | None
    actor_role: str | None
    occurred_at: datetime
    facts: WorkflowFacts


@dataclass(frozen=True, slots=True)
class DueTimer:
    """A durable deferred workflow command; it carries no clinical threshold."""

    id: UUID
    key: str
    due_at: datetime
    command_type: str
    facts_patch: Mapping[str, Any]
    status: DueTimerStatus = DueTimerStatus.SCHEDULED

    def __post_init__(self) -> None:
        """Validate timing and make timer payload independent from caller mutation."""
        object.__setattr__(self, "key", require_text(self.key, "timer key"))
        object.__setattr__(self, "command_type", require_text(self.command_type, "timer command"))
        object.__setattr__(self, "due_at", require_utc(self.due_at, "timer due_at"))
        object.__setattr__(self, "facts_patch", dict(self.facts_patch))


@dataclass(frozen=True, slots=True)
class GeneratedTask:
    """A deterministic instruction to create a human clinical work item."""

    id: UUID
    command_id: UUID
    effect_name: str
    task_type: str
    due_at: datetime | None


@dataclass(frozen=True, slots=True)
class GeneratedAlert:
    """A deterministic instruction to raise a review alert, never a diagnosis."""

    id: UUID
    command_id: UUID
    effect_name: str
    alert_type: str
    severity: str
    message: str


@dataclass(frozen=True, slots=True)
class TransitionExecution:
    """Pure result returned by the engine before the aggregate records it."""

    transition: Transition
    facts: WorkflowFacts
    tasks: tuple[GeneratedTask, ...]
    alerts: tuple[GeneratedAlert, ...]
    timers: tuple[DueTimer, ...]
