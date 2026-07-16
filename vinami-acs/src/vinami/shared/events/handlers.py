"""Dependency-injected internal handlers for safe audit and timeline projections."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from vinami.audit.adapters.persistence import AuditLogRecord, OutboxEventRecord
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.ecg.adapters.persistence import ECGStudyRecord
from vinami.patient.adapters.persistence import EncounterRecord
from vinami.shared.domain import utc_now
from vinami.shared.events.contracts import EventEnvelope
from vinami.timeline.adapters.persistence import TimelineEventRecord


class EventHandler(Protocol):
    """One synchronous, transaction-bound event handler contract."""

    @property
    def name(self) -> str:
        """Expose a stable consumer-idempotency key."""
        ...

    @property
    def event_type(self) -> str:
        """Expose the event type accepted by this handler."""
        ...

    def handle(self, event: EventEnvelope, session: Session) -> None:
        """Apply one idempotent local projection or side effect."""


class HandlerRegistry:
    """Registry populated in the composition root rather than through module globals."""

    def __init__(self) -> None:
        """Create an empty handler registry."""
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def register(self, handler: EventHandler) -> None:
        """Register one handler for its declared event type."""
        self._handlers[handler.event_type].append(handler)

    def handlers_for(self, event: EventEnvelope) -> tuple[EventHandler, ...]:
        """Return a stable snapshot of handlers for one event envelope."""
        return tuple(self._handlers.get(event.event_type, []))


@dataclass(frozen=True, slots=True)
class TimelineAuditProjectionHandler:
    """Project one event to append-only audit/timeline rows without changing clinical state."""

    event_type: str

    @property
    def name(self) -> str:
        """Expose a stable idempotency key for this projection handler."""
        return f"timeline_audit_projection:{self.event_type}"

    def handle(self, event: EventEnvelope, session: Session) -> None:
        """Persist projection rows only when this source event has not been projected already."""
        case_id = _case_id(event, session)
        audit_exists = session.scalar(
            select(AuditLogRecord.id).where(AuditLogRecord.source_event_id == event.event_id)
        )
        if audit_exists is None:
            session.add(
                AuditLogRecord(
                    case_id=case_id,
                    aggregate_type=event.aggregate_type,
                    aggregate_id=event.aggregate_id,
                    action=f"event:{event.event_type}",
                    actor_id=event.actor_id,
                    actor_role=(
                        str(event.metadata["actor_role"])
                        if event.metadata.get("actor_role") is not None
                        else None
                    ),
                    identity_subject=_optional_string(event.metadata.get("identity_subject")),
                    actor_roles=_string_list(event.metadata.get("actor_roles")),
                    applied_permission=_optional_string(event.metadata.get("applied_permission")),
                    identity_provider=_optional_string(event.metadata.get("identity_provider")),
                    authentication_method=_optional_string(
                        event.metadata.get("authentication_method")
                    ),
                    session_reference=_optional_string(event.metadata.get("session_reference")),
                    request_source=str(event.metadata.get("request_source", "internal")),
                    prior_version=_integer(event.payload.get("prior_version"))
                    or max(event.aggregate_version - 1, 0),
                    resulting_version=_integer(event.payload.get("resulting_version"))
                    or event.aggregate_version,
                    reason=(
                        str(event.payload["reason"])
                        if event.payload.get("reason") is not None
                        else None
                    ),
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    outcome="success",
                    occurred_at=event.occurred_at,
                    payload={
                        "event_version": event.event_version,
                        "correlation_id": str(event.correlation_id),
                        "causation_id": str(event.causation_id) if event.causation_id else None,
                        "payload": event.payload,
                        "metadata": event.metadata,
                    },
                    source_event_id=event.event_id,
                    idempotency_key=_optional_string(event.metadata.get("idempotency_key")),
                    authorization_result=_optional_string(
                        event.metadata.get("authorization_result")
                    )
                    or "authorized",
                    correction_status=_correction_status(event),
                    source_record_version=event.aggregate_version,
                )
            )
        if case_id is None:
            return
        timeline_exists = session.scalar(
            select(TimelineEventRecord.id).where(
                TimelineEventRecord.case_id == case_id,
                TimelineEventRecord.source_event_id == event.event_id,
            )
        )
        if timeline_exists is None:
            session.add(
                TimelineEventRecord(
                    case_id=case_id,
                    event_type=event.event_type,
                    title=_event_title(event.event_type),
                    occurred_at=event.occurred_at,
                    recorded_at=utc_now(),
                    source="transactional_outbox",
                    actor_id=event.actor_id,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                    payload={
                        "event_version": event.event_version,
                        "correlation_id": str(event.correlation_id),
                        "causation_id": str(event.causation_id) if event.causation_id else None,
                        "payload": event.payload,
                        "metadata": event.metadata,
                    },
                    source_event_id=event.event_id,
                    source_record_id=_source_record_id(event),
                    source_record_version=event.aggregate_version,
                    correction_status=_correction_status(event),
                    data_classification="clinical",
                )
            )
        if event.event_type == "ClinicalCaseOpened.v1":
            _project_case_ancestors(case_id, event, session)


def build_default_handler_registry() -> HandlerRegistry:
    """Register the initial catalog handlers through an explicit DI factory."""
    registry = HandlerRegistry()
    for event_type in (
        "PatientRegistered.v1",
        "EncounterStarted.v1",
        "ClinicalCaseOpened.v1",
        "SymptomsRecorded.v1",
        "VitalsRecorded.v1",
        "TriageAssessmentRecorded.v1",
        "TriageAssessmentCorrected.v1",
        "VitalObservationSetRecorded.v1",
        "VitalObservationSetCorrected.v1",
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
        "ECGIngestionRequested.v1",
        "ECGIngestionCompleted.v1",
        "ECGIngestionFailed.v1",
        "ECGIngestionRetried.v1",
        "ECGStudyCreated.v1",
        "ECGAnalysisRequested.v1",
        "ECGAnalysisCompleted.v1",
        "ECGAnalysisFailed.v1",
        "PhysicianECGInterpretationRecorded.v1",
        "PhysicianECGInterpretationCorrected.v1",
        "DynamicECGComparisonRequested.v1",
        "DynamicECGComparisonCompleted.v1",
        "DynamicECGComparisonFailed.v1",
        "DynamicECGPhysicianReviewRecorded.v1",
        "DynamicECGPhysicianReviewCorrected.v1",
        "RepeatECGReminderScheduled.v1",
        "RepeatECGReminderDue.v1",
        "RepeatECGReminderAcknowledged.v1",
        "RepeatECGReminderCompleted.v1",
        "RepeatECGReminderCancelled.v1",
        "TroponinResultRecorded.v1",
        "TroponinResultImported.v1",
        "TroponinResultPreliminaryReceived.v1",
        "TroponinResultFinalized.v1",
        "TroponinResultSourceAmended.v1",
        "TroponinResultAmended.v1",
        "LaboratoryImportRequested.v1",
        "LaboratoryImportCompleted.v1",
        "LaboratoryImportFailed.v1",
        "LaboratoryImportRetried.v1",
        "ClinicianTroponinReviewRecorded.v1",
        "ClinicianTroponinReviewCorrected.v1",
        "RepeatTroponinMeasurementRequested.v1",
        "RepeatTroponinMeasurementAcknowledged.v1",
        "RepeatTroponinMeasurementCompleted.v1",
        "RepeatTroponinMeasurementCancelled.v1",
        "ClinicalEvidenceSnapshotCreated.v1",
        "PhysicianClinicalAssessmentRecorded.v1",
        "PhysicianClinicalAssessmentCorrected.v1",
        "PhysicianClinicalDecisionRecorded.v1",
        "PhysicianClinicalDecisionCorrected.v1",
        "PhysicianClinicalDecisionRevoked.v1",
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
        "ResearchExportCompleted.v1",
        "IntegrationMessageReceived.v1",
        "IntegrationMessageProcessed.v1",
        "IntegrationMessageFailed.v1",
    ):
        registry.register(TimelineAuditProjectionHandler(event_type))
    return registry


def _case_id(event: EventEnvelope, session: Session) -> UUID | None:
    payload_case_id = event.payload.get("case_id")
    if isinstance(payload_case_id, str):
        try:
            return UUID(payload_case_id)
        except ValueError:
            return None
    if event.aggregate_type == "ClinicalCase":
        return event.aggregate_id
    study_id = event.payload.get("study_id")
    if isinstance(study_id, str):
        try:
            study = session.get(ECGStudyRecord, UUID(study_id))
        except ValueError:
            return None
        return study.case_id if study is not None else None
    return None


def _project_case_ancestors(case_id: UUID, event: EventEnvelope, session: Session) -> None:
    """Persist Patient and Encounter lifecycle events into a newly opened case timeline."""
    case_record = session.get(ClinicalCaseRecord, case_id)
    if case_record is None:
        return
    encounter = session.get(EncounterRecord, case_record.encounter_id)
    if encounter is None:
        return
    ancestor_events = session.scalars(
        select(OutboxEventRecord)
        .where(
            or_(
                (OutboxEventRecord.event_type == "PatientRegistered.v1")
                & (OutboxEventRecord.aggregate_id == encounter.patient_id),
                (OutboxEventRecord.event_type == "EncounterStarted.v1")
                & (OutboxEventRecord.aggregate_id == encounter.id),
            )
        )
        .order_by(OutboxEventRecord.occurred_at, OutboxEventRecord.event_id)
    ).all()
    for ancestor in ancestor_events:
        exists = session.scalar(
            select(TimelineEventRecord.id).where(
                TimelineEventRecord.case_id == case_id,
                TimelineEventRecord.source_event_id == ancestor.event_id,
            )
        )
        if exists is not None:
            continue
        session.add(
            TimelineEventRecord(
                case_id=case_id,
                event_type=ancestor.event_type,
                title=_event_title(ancestor.event_type),
                occurred_at=ancestor.occurred_at,
                recorded_at=utc_now(),
                source="transactional_outbox",
                actor_id=ancestor.actor_id,
                correlation_id=ancestor.correlation_id,
                causation_id=ancestor.causation_id,
                payload={
                    "event_version": ancestor.event_version,
                    "correlation_id": str(ancestor.correlation_id),
                    "causation_id": (str(ancestor.causation_id) if ancestor.causation_id else None),
                    "payload": ancestor.payload,
                    "metadata": ancestor.metadata_document,
                },
                source_event_id=ancestor.event_id,
                source_record_id=ancestor.aggregate_id,
                source_record_version=ancestor.aggregate_version,
                correction_status=_event_correction_status(ancestor.event_type),
                data_classification="clinical",
            )
        )


def _event_title(event_type: str) -> str:
    return {
        "PatientRegistered.v1": "Patient registered",
        "EncounterStarted.v1": "Encounter started",
        "ClinicalCaseOpened.v1": "Suspected ACS case opened",
        "TriageAssessmentRecorded.v1": "Triage assessment recorded",
        "TriageAssessmentCorrected.v1": "Triage assessment corrected",
        "VitalObservationSetRecorded.v1": "Vital observations recorded",
        "VitalObservationSetCorrected.v1": "Vital observations corrected",
        "CaseClosed.v1": "Clinical case closed",
        "ECGIngestionRequested.v1": "ECG ingestion requested",
        "ECGIngestionCompleted.v1": "ECG received and parsed",
        "ECGIngestionFailed.v1": "ECG ingestion requires review",
        "ECGIngestionRetried.v1": "ECG ingestion retried",
        "ECGStudyCreated.v1": "ECG study created",
        "ECGQualityAssessed.v1": "ECG technical quality assessed",
        "ECGAnalysisRequested.v1": "AI-supported ECG analysis requested",
        "ECGAnalysisCompleted.v1": "AI-supported ECG analysis completed",
        "ECGAnalysisFailed.v1": "AI-supported ECG analysis failed",
        "PhysicianECGInterpretationRecorded.v1": "Physician ECG interpretation recorded",
        "PhysicianECGInterpretationCorrected.v1": "Physician ECG interpretation corrected",
        "DynamicECGComparisonCompleted.v1": "Serial ECG technical comparison completed",
        "DynamicECGComparisonFailed.v1": "Serial ECG pair was not comparable",
        "DynamicECGPhysicianReviewRecorded.v1": "Physician reviewed serial ECG comparison",
        "DynamicECGPhysicianReviewCorrected.v1": "Physician serial ECG review corrected",
        "RepeatECGReminderScheduled.v1": "Repeat ECG review requested",
        "RepeatECGReminderAcknowledged.v1": "Repeat ECG reminder acknowledged",
        "RepeatECGReminderCompleted.v1": "Repeat ECG completed",
        "RepeatECGReminderCancelled.v1": "Repeat ECG reminder cancelled",
        "ClinicalEvidenceSnapshotCreated.v1": "Clinical evidence snapshot created",
        "PhysicianClinicalAssessmentRecorded.v1": "Physician clinical assessment recorded",
        "PhysicianClinicalAssessmentCorrected.v1": "Physician clinical assessment corrected",
        "PhysicianClinicalDecisionRecorded.v1": "Physician clinical decision recorded",
        "PhysicianClinicalDecisionCorrected.v1": "Physician clinical decision corrected",
        "PhysicianClinicalDecisionRevoked.v1": "Physician clinical decision revoked",
        "ClinicalTaskCreated.v1": "Clinical task created",
        "ClinicalTaskTransitioned.v1": "Clinical task status changed",
        "ClinicalTaskCompleted.v1": "Clinical task completed",
        "ClinicalTaskCancelled.v1": "Clinical task cancelled",
        "ClinicalTaskOverdue.v1": "Clinical task overdue",
        "ClinicalTaskEscalated.v1": "Clinical task escalated",
        "ClinicalAlertRaised.v1": "Operational alert raised",
        "ClinicalAlertAcknowledged.v1": "Operational alert acknowledged",
        "ClinicalAlertResolved.v1": "Operational alert resolved",
        "ClinicalAlertEscalated.v1": "Operational alert escalated",
        "ClinicalOutcomeRecorded.v1": "Clinical outcome recorded",
        "ClinicalOutcomeCorrected.v1": "Clinical outcome corrected",
        "ResearchExportCompleted.v1": "Research export generated",
        "IntegrationMessageReceived.v1": "Integration message received",
        "IntegrationMessageProcessed.v1": "Integration message processed",
        "IntegrationMessageFailed.v1": "Integration message failed",
    }.get(event_type, event_type.removesuffix(".v1"))


def _source_record_id(event: EventEnvelope) -> UUID:
    for key in (
        "outcome_id",
        "result_id",
        "analysis_id",
        "assessment_id",
        "decision_id",
        "task_id",
        "alert_id",
        "study_id",
        "snapshot_id",
        "message_id",
    ):
        value = event.payload.get(key)
        if isinstance(value, str):
            try:
                return UUID(value)
            except ValueError:
                continue
    return event.aggregate_id


def _correction_status(event: EventEnvelope) -> str:
    payload = event.payload
    if any(
        payload.get(key) is not None for key in ("supersedes_outcome_id", "corrects_decision_id")
    ):
        return "correction"
    return _event_correction_status(event.event_type)


def _event_correction_status(event_type: str) -> str:
    if "Revoked" in event_type:
        return "revocation"
    if "Corrected" in event_type or "Amended" in event_type:
        return "correction"
    return "original"


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def registered_handler_names(registry: HandlerRegistry, event_types: Iterable[str]) -> set[str]:
    """Return handler names for diagnostics without exposing mutable registry internals."""
    names: set[str] = set()
    for event_type in event_types:
        envelope = EventEnvelope(
            event_type=event_type,
            aggregate_type="Diagnostic",
            aggregate_id=UUID(int=0),
            aggregate_version=1,
            payload={},
        )
        names.update(handler.name for handler in registry.handlers_for(envelope))
    return names
