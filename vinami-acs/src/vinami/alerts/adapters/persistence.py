"""SQLAlchemy mapping and repository for case-associated safety alerts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.alerts.domain.model import Alert, AlertSeverity, AlertStatus
from vinami.shared.persistence import Base, UTCDateTime, UUIDType


class AlertRecord(Base):
    """Persisted alert history; resolution does not remove an alert row."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "workflow_command_id",
            "workflow_effect",
            name="uq_alert_workflow_effect",
        ),
    )

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_command_id: Mapped[UUID | None] = mapped_column(UUIDType, nullable=True)
    workflow_effect: Mapped[str | None] = mapped_column(String(160), nullable=True)
    alert_type: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"), nullable=False
    )
    message: Mapped[str] = mapped_column(String(4000), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"), nullable=False, index=True
    )
    raised_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("clinical_users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)


def alert_from_record(record: AlertRecord) -> Alert:
    """Rehydrate an alert without replaying event history."""
    return Alert(
        id=record.id,
        case_id=record.case_id,
        alert_type=record.alert_type,
        source=record.source,
        severity=record.severity,
        message=record.message,
        status=record.status,
        raised_at=record.raised_at,
        acknowledged_by=record.acknowledged_by,
        acknowledged_at=record.acknowledged_at,
        resolved_by=record.resolved_by,
        resolved_at=record.resolved_at,
        resolution_reason=record.resolution_reason,
    )


class SQLAlchemyAlertRepository:
    """Alert repository bound to one explicit transaction session."""

    def __init__(self, session: Session) -> None:
        """Bind repository work to an active unit of work."""
        self._session = session

    def add(self, alert: Alert) -> None:
        """Insert a raised alert with its initial status."""
        self._session.add(
            AlertRecord(
                id=alert.id,
                case_id=alert.case_id,
                workflow_id=None,
                workflow_command_id=None,
                workflow_effect=None,
                alert_type=alert.alert_type,
                source=alert.source,
                severity=alert.severity,
                message=alert.message,
                status=alert.status,
                raised_at=alert.raised_at,
                acknowledged_by=alert.acknowledged_by,
                acknowledged_at=alert.acknowledged_at,
                resolved_by=alert.resolved_by,
                resolved_at=alert.resolved_at,
                resolution_reason=alert.resolution_reason,
            )
        )

    def get(self, alert_id: UUID) -> Alert | None:
        """Retrieve one alert by UUID."""
        record = self._session.get(AlertRecord, alert_id)
        return alert_from_record(record) if record is not None else None

    def save(self, alert: Alert) -> None:
        """Persist acknowledgement or resolution fields."""
        record = self._session.get(AlertRecord, alert.id)
        if record is None:
            raise ValueError(f"alert {alert.id} does not exist")
        record.status = alert.status
        record.acknowledged_by = alert.acknowledged_by
        record.acknowledged_at = alert.acknowledged_at
        record.resolved_by = alert.resolved_by
        record.resolved_at = alert.resolved_at
        record.resolution_reason = alert.resolution_reason
