"""SQLAlchemy read adapter for real-time notifications."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from vinami.audit.adapters.persistence import OutboxEventRecord
from vinami.integration.application.realtime import RealtimeNotification

REALTIME_EVENT_TYPES = frozenset(
    {
        "ECGStudyCreated.v1",
        "ECGIngestionCompleted.v1",
        "ECGAnalysisCompleted.v1",
        "PhysicianECGInterpretationRecorded.v1",
        "PhysicianECGInterpretationCorrected.v1",
        "TroponinResultRecorded.v1",
        "TroponinResultImported.v1",
        "TroponinResultFinalized.v1",
        "TroponinResultAmended.v1",
        "PhysicianClinicalAssessmentRecorded.v1",
        "PhysicianClinicalAssessmentCorrected.v1",
        "PhysicianClinicalDecisionRecorded.v1",
        "PhysicianClinicalDecisionCorrected.v1",
        "PhysicianClinicalDecisionRevoked.v1",
        "WorkflowTransitioned.v1",
        "ClinicalTaskCreated.v1",
        "ClinicalTaskTransitioned.v1",
        "ClinicalTaskCompleted.v1",
        "ClinicalTaskCancelled.v1",
        "ClinicalTaskOverdue.v1",
        "ClinicalTaskEscalated.v1",
        "ClinicalAlertRaised.v1",
        "ClinicalAlertAcknowledged.v1",
        "ClinicalAlertResolved.v1",
        "ClinicalAlertEscalated.v1",
        "ClinicalOutcomeRecorded.v1",
        "ClinicalOutcomeCorrected.v1",
        "IntegrationMessageProcessed.v1",
        "IntegrationMessageFailed.v1",
    }
)


class SQLAlchemyRealtimeEventRepository:
    """Read committed outbox events as reconnect-safe notifications."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def events_since(
        self, last_event_id: UUID | None, case_id: UUID | None, limit: int
    ) -> list[RealtimeNotification]:
        with self._session_factory() as session:
            statement = select(OutboxEventRecord).where(
                OutboxEventRecord.event_type.in_(REALTIME_EVENT_TYPES)
            )
            if last_event_id is not None:
                anchor = session.scalar(
                    select(OutboxEventRecord).where(OutboxEventRecord.event_id == last_event_id)
                )
                if anchor is not None:
                    statement = statement.where(
                        or_(
                            OutboxEventRecord.occurred_at > anchor.occurred_at,
                            and_(
                                OutboxEventRecord.occurred_at == anchor.occurred_at,
                                OutboxEventRecord.id > anchor.id,
                            ),
                        )
                    )
            if case_id is not None:
                statement = statement.where(
                    or_(
                        OutboxEventRecord.payload["case_id"].as_string() == str(case_id),
                        and_(
                            OutboxEventRecord.aggregate_type == "ClinicalCase",
                            OutboxEventRecord.aggregate_id == case_id,
                        ),
                    )
                )
            rows = session.scalars(
                statement.order_by(OutboxEventRecord.occurred_at, OutboxEventRecord.id).limit(limit)
            ).all()
            return [_notification(row) for row in rows]


def _notification(row: OutboxEventRecord) -> RealtimeNotification:
    case_value = row.payload.get("case_id")
    case_id = UUID(str(case_value)) if case_value else None
    return RealtimeNotification(
        event_id=row.event_id,
        event_type=row.event_type,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        occurred_at=row.occurred_at,
        case_id=case_id,
        resource_hint=_resource_hint(row.event_type),
        correlation_id=row.correlation_id,
    )


def _resource_hint(event_type: str) -> str:
    if event_type.startswith(("ECG", "PhysicianECG", "DynamicECG")):
        return "ecg"
    if event_type.startswith(("Troponin", "Laboratory", "ClinicianTroponin")):
        return "troponin"
    if event_type.startswith("ClinicalTask"):
        return "tasks"
    if event_type.startswith("ClinicalAlert"):
        return "alerts"
    if event_type.startswith("PhysicianClinical"):
        return "clinical_reasoning"
    if event_type.startswith("ClinicalOutcome"):
        return "outcomes"
    if event_type.startswith("IntegrationMessage"):
        return "integration"
    return "case"
