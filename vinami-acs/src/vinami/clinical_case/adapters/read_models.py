"""SQLAlchemy lifecycle read-model adapter."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from vinami.audit.adapters.persistence import AuditLogRecord
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.clinical_case.ports.read_models import AuditReadRecord, TimelineReadRecord
from vinami.patient.adapters.persistence import EncounterRecord
from vinami.timeline.adapters.persistence import TimelineEventRecord


class SQLAlchemyClinicalLifecycleReadRepository:
    """Read lifecycle projections through one transaction-bound SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def timeline_for_case(self, case_id: UUID) -> list[TimelineReadRecord]:
        records = self._session.scalars(
            select(TimelineEventRecord)
            .where(TimelineEventRecord.case_id == case_id)
            .order_by(TimelineEventRecord.occurred_at, TimelineEventRecord.id)
        ).all()
        return [
            TimelineReadRecord(
                timeline_event_id=record.id,
                case_id=record.case_id,
                event_type=record.event_type,
                title=record.title,
                occurred_at=record.occurred_at,
                recorded_at=record.recorded_at,
                source=record.source,
                actor_id=record.actor_id,
                correlation_id=record.correlation_id,
                causation_id=record.causation_id,
            )
            for record in records
        ]

    def audit_for_case(self, case_id: UUID) -> list[AuditReadRecord]:
        case = self._session.get(ClinicalCaseRecord, case_id)
        if case is None:
            return []
        encounter = self._session.get(EncounterRecord, case.encounter_id)
        if encounter is None:
            return []
        records = self._session.scalars(
            select(AuditLogRecord)
            .where(
                or_(
                    AuditLogRecord.case_id == case.id,
                    (AuditLogRecord.aggregate_type == "Patient")
                    & (AuditLogRecord.aggregate_id == encounter.patient_id),
                    (AuditLogRecord.aggregate_type == "Encounter")
                    & (AuditLogRecord.aggregate_id == encounter.id),
                    (AuditLogRecord.aggregate_type == "ClinicalCase")
                    & (AuditLogRecord.aggregate_id == case.id),
                )
            )
            .order_by(AuditLogRecord.occurred_at, AuditLogRecord.id)
        ).all()
        return [
            AuditReadRecord(
                audit_id=record.id,
                actor_id=record.actor_id,
                actor_role=record.actor_role,
                identity_subject=record.identity_subject,
                actor_roles=tuple(record.actor_roles),
                applied_permission=record.applied_permission,
                identity_provider=record.identity_provider,
                authentication_method=record.authentication_method,
                session_reference=record.session_reference,
                action=record.action,
                resource_type=record.aggregate_type,
                resource_id=record.aggregate_id,
                request_source=record.request_source,
                correlation_id=record.correlation_id,
                causation_id=record.causation_id,
                prior_version=record.prior_version,
                resulting_version=record.resulting_version,
                outcome=record.outcome,
                reason=record.reason,
                recorded_at=record.occurred_at,
            )
            for record in records
        ]
