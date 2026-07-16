"""Safety alert aggregate with append-only acknowledgement and resolution provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
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
from vinami.shared.events.contracts import EventContext


class AlertSeverity(StrEnum):
    """Operational severity used for review prioritization, not diagnostic certainty."""

    INFORMATION = "information"
    REVIEW = "review"
    URGENT = "urgent"


class AlertStatus(StrEnum):
    """Alert lifecycle preserving acknowledgement and resolution history."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class AlertTransition:
    """Immutable alert lifecycle transition."""

    transition_id: UUID
    from_status: AlertStatus
    to_status: AlertStatus
    actor_id: UUID
    occurred_at: datetime
    reason: str | None = None


@dataclass(slots=True)
class Alert(AggregateRoot):
    """Alert aggregate that cannot diagnose, close a case, or invoke AI."""

    case_id: UUID
    alert_type: str
    source: str
    severity: AlertSeverity
    message: str
    status: AlertStatus
    raised_at: datetime
    acknowledged_by: UUID | None = None
    acknowledged_at: datetime | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    resolution_reason: str | None = None
    workflow_id: UUID | None = None
    task_id: UUID | None = None
    deduplication_key: str | None = None
    version: int = 1
    escalation_level: int = 0
    transitions: list[AlertTransition] = field(default_factory=list)

    @classmethod
    def raise_alert(
        cls,
        case_id: UUID,
        alert_type: str,
        source: str,
        severity: AlertSeverity,
        message: str,
        raised_at: datetime | None = None,
        alert_id: UUID | None = None,
        workflow_id: UUID | None = None,
        task_id: UUID | None = None,
        deduplication_key: str | None = None,
    ) -> Alert:
        """Raise an active review alert with an explicit source."""
        alert = cls(
            id=alert_id or uuid4(),
            case_id=case_id,
            alert_type=require_text(alert_type, "alert_type"),
            source=require_text(source, "alert source"),
            severity=severity,
            message=require_text(message, "alert message"),
            status=AlertStatus.ACTIVE,
            raised_at=require_utc(raised_at or utc_now(), "raised_at"),
            workflow_id=workflow_id,
            task_id=task_id,
            deduplication_key=(
                require_text(deduplication_key, "deduplication_key") if deduplication_key else None
            ),
        )
        alert._record_event(
            "AlertRaised.v1",
            1,
            {"alert_id": str(alert.id), "case_id": str(case_id), "severity": severity.value},
        )
        return alert

    def acknowledge(self, actor_id: UUID, acknowledged_at: datetime | None = None) -> None:
        """Acknowledge an active alert without removing it from history."""
        if self.status is not AlertStatus.ACTIVE:
            raise DomainInvariantError("only an active alert can be acknowledged")
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_by = actor_id
        self.acknowledged_at = require_utc(acknowledged_at or utc_now(), "acknowledged_at")
        self.version += 1
        self.transitions.append(
            AlertTransition(
                uuid4(),
                AlertStatus.ACTIVE,
                AlertStatus.ACKNOWLEDGED,
                actor_id,
                self.acknowledged_at,
            )
        )
        self._record_event(
            "ClinicalAlertAcknowledged.v1",
            self.version,
            {"alert_id": str(self.id), "case_id": str(self.case_id), "actor_id": str(actor_id)},
            EventContext.start(actor_id=actor_id),
        )

    def resolve(self, actor_id: UUID, reason: str, resolved_at: datetime | None = None) -> None:
        """Resolve an acknowledged alert while retaining provenance."""
        if self.status is not AlertStatus.ACKNOWLEDGED:
            raise DomainInvariantError("only an acknowledged alert can be resolved")
        self.status = AlertStatus.RESOLVED
        self.resolved_by = actor_id
        self.resolved_at = require_utc(resolved_at or utc_now(), "resolved_at")
        self.resolution_reason = require_text(reason, "resolution_reason")
        self.version += 1
        self.transitions.append(
            AlertTransition(
                uuid4(),
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.RESOLVED,
                actor_id,
                self.resolved_at,
                self.resolution_reason,
            )
        )
        self._record_event(
            "ClinicalAlertResolved.v1",
            self.version,
            {
                "alert_id": str(self.id),
                "case_id": str(self.case_id),
                "actor_id": str(actor_id),
                "reason": self.resolution_reason,
            },
            EventContext.start(actor_id=actor_id),
        )

    def escalate(self, actor_id: UUID) -> None:
        """Increase operational escalation without changing clinical authority."""
        if self.status is AlertStatus.RESOLVED:
            raise DomainInvariantError("a resolved alert cannot be escalated")
        self.escalation_level += 1
        self.version += 1
        self._record_event(
            "ClinicalAlertEscalated.v1",
            self.version,
            {
                "alert_id": str(self.id),
                "case_id": str(self.case_id),
                "escalation_level": self.escalation_level,
            },
            EventContext.start(actor_id=actor_id),
        )
