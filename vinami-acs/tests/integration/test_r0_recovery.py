"""R0 regression tests for production bootstrap, provenance, events, and audit integrity."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from vinami.alerts.adapters.persistence import AlertRecord
from vinami.alerts.domain.model import AlertSeverity, AlertStatus
from vinami.audit.adapters.persistence import AuditLogRecord, OutboxEventRecord, OutcomeRecord
from vinami.audit.adapters.writer import SQLAlchemyAuditWriter
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.clinical_case.application.closure import (
    CloseClinicalCase,
    CloseClinicalCaseHandler,
)
from vinami.clinical_case.domain.model import CaseStatus, ClinicalCase, ClinicalPriority
from vinami.ecg.domain.model import (
    ECGAcquisitionMetadata,
    ECGAIResult,
    ECGFinding,
    ECGStudy,
)
from vinami.identity.adapters.persistence import ClinicalUserRecord
from vinami.identity.domain.model import ClinicalRole
from vinami.patient.domain.model import (
    Demographics,
    Encounter,
    Patient,
    PatientIdentifier,
    PersonName,
)
from vinami.shared.actor import ActorContext
from vinami.shared.config import Settings
from vinami.shared.container import AppContainer
from vinami.shared.domain import DomainInvariantError
from vinami.shared.events.dispatcher import InternalEventDispatcher
from vinami.shared.events.handlers import build_default_handler_registry
from vinami.shared.events.registry import EventRegistry
from vinami.shared.events.serializer import EventSerializer
from vinami.shared.orm_registry import initialize_mappings
from vinami.shared.unit_of_work import SQLAlchemyUnitOfWork
from vinami.timeline.adapters.persistence import TimelineEventRecord
from vinami.troponin.domain.model import (
    TroponinAssay,
    TroponinMeasurement,
    TroponinQualityFlag,
    TroponinTimeline,
)
from vinami.workflow.adapters.decision_persistence import PhysicianDecisionRecord
from vinami.workflow.adapters.persistence import ClinicalTaskRecord
from vinami.workflow.application.commands import WorkflowCommandHandler
from vinami.workflow.application.decisions import (
    RecordPhysicianDecision,
    RecordPhysicianDecisionHandler,
)
from vinami.workflow.application.definitions import load_demo_workflow_definition
from vinami.workflow.domain.decision import (
    PhysicianDecision,
    PhysicianDecisionStatus,
    PhysicianDecisionType,
)
from vinami.workflow.domain.definition import WorkflowCommand, WorkflowState
from vinami.workflow.domain.model import TaskStatus

NOW = datetime(2026, 7, 13, 1, 0, tzinfo=UTC)


def _case_graph() -> tuple[Patient, Encounter, ClinicalCase]:
    patient = Patient.register(
        PatientIdentifier("r0-integration", f"P-{uuid4()}"),
        PersonName("Lan", "Nguyen"),
        Demographics(None, None),
        NOW,
    )
    encounter = Encounter.start(patient.id, "Emergency", NOW)
    clinical_case = ClinicalCase.open(
        encounter.id, "R0 recovery verification", ClinicalPriority.URGENT, NOW
    )
    return patient, encounter, clinical_case


def _persist_case(factory: sessionmaker[Session]) -> ClinicalCase:
    patient, encounter, clinical_case = _case_graph()
    with SQLAlchemyUnitOfWork(factory) as unit_of_work:
        unit_of_work.patients.add(patient)
        unit_of_work.encounters.add(encounter)
        unit_of_work.cases.add(clinical_case)
        unit_of_work.collect_events((patient, encounter, clinical_case))
        unit_of_work.commit()
    return clinical_case


def test_production_composition_root_loads_complete_mapping_registry(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Production composition, not fixture import order, resolves every critical mapping."""
    metadata = initialize_mappings()
    database_url = postgres_session_factory.kw["bind"].url.render_as_string(hide_password=False)
    settings = Settings(database_url=database_url, identity_mode="development")
    container = AppContainer.create(settings)
    try:
        assert {
            "clinical_users",
            "clinical_cases",
            "clinical_workflows",
            "physician_decisions",
            "audit_logs",
            "outbox_events",
        } <= set(metadata.tables)
        container.database.probe_readiness()
    finally:
        container.database.dispose()


def test_ecg_and_troponin_provenance_round_trip(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """No required source, acquisition, model, assay, timing, or quality field is dropped."""
    clinical_case = _persist_case(postgres_session_factory)
    ecg = ECGStudy.upload(
        case_id=clinical_case.id,
        input_reference=f"evidence://ecg/{uuid4()}",
        media_type="application/wfdb",
        metadata=ECGAcquisitionMetadata(
            device_name="Demo ECG 12L",
            sampling_hz=500,
            lead_count=12,
            acquired_at=NOW,
            source_system="demo-ehr",
            source_record_id="ECG-R0-001",
            device_vendor="Demo Vendor",
            input_format="WFDB",
            lead_configuration="12-lead standard",
        ),
        uploaded_at=NOW,
    )
    ecg.record_ai_result(
        ECGAIResult(
            model_name="mock-convnext",
            model_version="r0",
            provider_name="mock-provider",
            input_reference=ecg.input_reference,
            analyzed_at=NOW,
            findings=(ECGFinding("MI-related ECG pattern", 0.2, 0.5),),
            limitations="Research-use evidence only.",
        )
    )
    timeline = TroponinTimeline.create(clinical_case.id)
    timeline.order("LAB-R0-001", NOW)
    timeline.collect("LAB-R0-001", NOW)
    timeline.record_result(
        TroponinMeasurement(
            id=uuid4(),
            value=12.5,
            assay=TroponinAssay(
                "demo hs-cTn",
                "ng/L",
                manufacturer="Demo Lab",
                analyzer="Analyzer R0",
                reference_limit=10.0,
            ),
            collected_at=NOW,
            resulted_at=NOW,
            order_reference="LAB-R0-001",
            quality_flags=(TroponinQualityFlag.MANUAL_REVIEW,),
            renal_function_context="not supplied",
            source_system="demo-lis",
            source_record_id="RESULT-R0-001",
            ingested_at=NOW,
            reference_metadata=(("population", "demo"),),
        )
    )
    with SQLAlchemyUnitOfWork(postgres_session_factory) as unit_of_work:
        unit_of_work.ecg_studies.add(ecg)
        unit_of_work.troponin_timelines.add(timeline)
        unit_of_work.commit()
    with SQLAlchemyUnitOfWork(postgres_session_factory) as unit_of_work:
        restored_ecg = unit_of_work.ecg_studies.get(ecg.id)
        restored_troponin = unit_of_work.troponin_timelines.get_by_case_id(clinical_case.id)

    assert restored_ecg is not None and restored_ecg.ai_result is not None
    assert restored_ecg.metadata == ecg.metadata
    assert restored_ecg.uploaded_at == ecg.uploaded_at
    assert restored_ecg.ai_result.provider_name == "mock-provider"
    assert restored_ecg.ai_result.model_version == "r0"
    assert restored_troponin is not None
    assert restored_troponin.ordered_at_by_reference["LAB-R0-001"] == NOW
    assert restored_troponin.collected_at_by_reference["LAB-R0-001"] == NOW
    assert restored_troponin.measurements[0] == timeline.measurements[0]


def test_foundational_events_create_idempotent_audit_and_case_timeline(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Patient, encounter, and case lifecycle events are no longer silently unhandled."""
    clinical_case = _persist_case(postgres_session_factory)
    dispatcher = InternalEventDispatcher(
        session_factory=postgres_session_factory,
        serializer=EventSerializer(EventRegistry.default()),
        handlers=build_default_handler_registry(),
        logger=structlog.get_logger("r0-event-test"),
        max_retries=3,
        retry_delay_seconds=0,
        claim_ttl_seconds=60,
    )
    first = dispatcher.dispatch_pending()
    second = dispatcher.dispatch_pending()

    assert first.published >= 3
    assert first.dead_lettered == 0
    assert second.published == 0
    with postgres_session_factory() as session:
        source_events = list(
            session.scalars(
                select(OutboxEventRecord.event_id).where(
                    OutboxEventRecord.aggregate_id.in_(
                        [clinical_case.id, clinical_case.encounter_id]
                    )
                )
            )
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLogRecord)
                .where(AuditLogRecord.source_event_id.in_(source_events))
            )
            >= 2
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(TimelineEventRecord)
                .where(TimelineEventRecord.case_id == clinical_case.id)
            )
            >= 1
        )


def test_persisted_authorized_decision_is_required_for_cath_lab_review(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Require exact persisted physician authority before cath-lab review."""
    clinical_case = _persist_case(postgres_session_factory)
    actor_id = uuid4()
    with postgres_session_factory() as session:
        session.add(
            ClinicalUserRecord(
                id=actor_id,
                display_name="R0 Physician",
                role=ClinicalRole.PHYSICIAN,
                team_id=None,
            )
        )
        session.commit()

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(postgres_session_factory)

    audit_writer = SQLAlchemyAuditWriter(postgres_session_factory)
    definition = load_demo_workflow_definition()
    workflow_handler = WorkflowCommandHandler(uow_factory, definition, audit_writer=audit_writer)
    decision_handler = RecordPhysicianDecisionHandler(uow_factory, audit_writer)
    workflow = workflow_handler.start(clinical_case.id)
    workflow_handler.execute(workflow.id, WorkflowCommand("start_triage", 1, issued_at=NOW))
    workflow_handler.execute(workflow.id, WorkflowCommand("complete_triage", 2, issued_at=NOW))
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "record_ecg",
            3,
            facts_patch={"ecg_available": True, "ecg_quality_acceptable": True},
            issued_at=NOW,
        ),
    )
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand("request_troponin", 4, due_at=NOW, issued_at=NOW),
    )
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "record_troponin", 5, facts_patch={"troponin_available": True}, issued_at=NOW
        ),
    )
    workflow_handler.execute(workflow.id, WorkflowCommand("select_demo_pathway", 6, issued_at=NOW))
    actor = ActorContext.for_actor(actor_id, "physician")
    pathway_decision_id = uuid4()
    decision_handler.execute(
        RecordPhysicianDecision(
            decision_id=pathway_decision_id,
            clinical_case_id=clinical_case.id,
            workflow_id=workflow.id,
            actor=actor,
            decision_type=PhysicianDecisionType.PATHWAY_ACCEPTED,
            decision_status=PhysicianDecisionStatus.ACTIVE,
            reason_code="reviewed-demo-pathway",
            evidence_snapshot_reference="evidence://snapshot/pathway",
            workflow_version=7,
            aggregate_expected_version=1,
            occurred_at=NOW,
        ),
        recorded_at=NOW,
    )
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "record_physician_decision",
            7,
            actor_id=actor_id,
            actor_role="physician",
            decision_id=pathway_decision_id,
            case_expected_version=1,
            correlation_id=actor.correlation_id,
            issued_at=NOW,
        ),
    )

    missing_command = WorkflowCommand(
        "request_cath_lab_review",
        8,
        actor_id=actor_id,
        actor_role="physician",
        decision_id=uuid4(),
        case_expected_version=1,
        issued_at=NOW,
    )
    with pytest.raises(DomainInvariantError, match="persisted physician decision"):
        workflow_handler.execute(workflow.id, missing_command)

    cath_decision_id = uuid4()
    cath_actor = ActorContext.for_actor(actor_id, "physician")
    decision_handler.execute(
        RecordPhysicianDecision(
            decision_id=cath_decision_id,
            clinical_case_id=clinical_case.id,
            workflow_id=workflow.id,
            actor=cath_actor,
            decision_type=PhysicianDecisionType.CATH_LAB_REVIEW_REQUESTED,
            decision_status=PhysicianDecisionStatus.ACTIVE,
            reason_code="physician-requested-review",
            evidence_snapshot_reference="evidence://snapshot/cath-review",
            workflow_version=8,
            aggregate_expected_version=1,
            occurred_at=NOW,
        ),
        recorded_at=NOW,
    )
    result = workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "request_cath_lab_review",
            8,
            actor_id=actor_id,
            actor_role="physician",
            decision_id=cath_decision_id,
            case_expected_version=1,
            correlation_id=cath_actor.correlation_id,
            issued_at=NOW,
        ),
    )
    assert result.state is WorkflowState.CATH_LAB_REVIEW
    with postgres_session_factory() as session:
        assert session.get(PhysicianDecisionRecord, cath_decision_id) is not None


def test_non_physician_actor_cannot_persist_decision(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """A persisted nurse identity cannot self-assert physician authority."""
    clinical_case = _persist_case(postgres_session_factory)
    actor_id = uuid4()
    with postgres_session_factory() as session:
        session.add(
            ClinicalUserRecord(
                id=actor_id,
                display_name="R0 Nurse",
                role=ClinicalRole.NURSE,
                team_id=None,
            )
        )
        session.commit()

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(postgres_session_factory)

    audit_writer = SQLAlchemyAuditWriter(postgres_session_factory)
    workflow = WorkflowCommandHandler(uow_factory, load_demo_workflow_definition()).start(
        clinical_case.id
    )
    decision_id = uuid4()
    command = RecordPhysicianDecision(
        decision_id=decision_id,
        clinical_case_id=clinical_case.id,
        workflow_id=workflow.id,
        actor=ActorContext.for_actor(actor_id, "nurse"),
        decision_type=PhysicianDecisionType.PATHWAY_ACCEPTED,
        decision_status=PhysicianDecisionStatus.ACTIVE,
        reason_code="unauthorized",
        evidence_snapshot_reference="evidence://snapshot/unauthorized",
        workflow_version=1,
        aggregate_expected_version=1,
        occurred_at=NOW,
    )
    with pytest.raises(DomainInvariantError, match="not authorized"):
        RecordPhysicianDecisionHandler(uow_factory, audit_writer).execute(command, recorded_at=NOW)
    with postgres_session_factory() as session:
        assert session.get(PhysicianDecisionRecord, decision_id) is None
        rejected = session.get(AuditLogRecord, decision_id)
        assert rejected is not None and rejected.outcome == "rejected"


def test_append_only_revocation_invalidates_the_original_decision(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """A later revocation makes the original active decision unusable by guards."""
    clinical_case = _persist_case(postgres_session_factory)
    actor_id = uuid4()
    original_id = uuid4()
    with postgres_session_factory() as session:
        session.add(
            ClinicalUserRecord(
                id=actor_id,
                display_name="R0 Revoking Physician",
                role=ClinicalRole.PHYSICIAN,
                team_id=None,
            )
        )
        session.commit()

    original = PhysicianDecision(
        decision_id=original_id,
        clinical_case_id=clinical_case.id,
        actor_id=actor_id,
        actor_role="physician",
        decision_type=PhysicianDecisionType.CATH_LAB_REVIEW_REQUESTED,
        decision_status=PhysicianDecisionStatus.ACTIVE,
        reason_code="review_requested",
        note=None,
        evidence_snapshot_reference="evidence://snapshot/original",
        workflow_version=1,
        aggregate_expected_version=1,
        occurred_at=NOW,
        recorded_at=NOW,
        correlation_id=uuid4(),
        causation_id=None,
        corrects_decision_id=None,
    )
    revocation = PhysicianDecision(
        decision_id=uuid4(),
        clinical_case_id=clinical_case.id,
        actor_id=actor_id,
        actor_role="physician",
        decision_type=PhysicianDecisionType.CATH_LAB_REVIEW_REQUESTED,
        decision_status=PhysicianDecisionStatus.REVOKED,
        reason_code="entered_in_error",
        note="Append-only correction",
        evidence_snapshot_reference="evidence://snapshot/revocation",
        workflow_version=1,
        aggregate_expected_version=1,
        occurred_at=NOW,
        recorded_at=NOW,
        correlation_id=uuid4(),
        causation_id=None,
        corrects_decision_id=original_id,
    )
    with SQLAlchemyUnitOfWork(postgres_session_factory) as unit_of_work:
        unit_of_work.physician_decisions.add(original)
        unit_of_work.physician_decisions.add(revocation)
        unit_of_work.commit()

    with SQLAlchemyUnitOfWork(postgres_session_factory) as unit_of_work:
        assert unit_of_work.physician_decisions.is_effective(original_id) is False


def test_coordinated_case_closure_is_blocked_by_unresolved_critical_alert(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Closure changes neither workflow nor case until alert/task/outcome safeguards pass."""
    clinical_case = _persist_case(postgres_session_factory)
    actor_id = uuid4()
    with postgres_session_factory() as session:
        session.add(
            ClinicalUserRecord(
                id=actor_id,
                display_name="R0 Closing Physician",
                role=ClinicalRole.PHYSICIAN,
                team_id=None,
            )
        )
        session.commit()
    with SQLAlchemyUnitOfWork(postgres_session_factory) as unit_of_work:
        current_case = unit_of_work.cases.get(clinical_case.id)
        assert current_case is not None
        current_case.begin_review(1)
        unit_of_work.cases.save(current_case)
        unit_of_work.commit()

    def uow_factory() -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(postgres_session_factory)

    audit_writer = SQLAlchemyAuditWriter(postgres_session_factory)
    workflow_handler = WorkflowCommandHandler(
        uow_factory, load_demo_workflow_definition(), audit_writer=audit_writer
    )
    decision_handler = RecordPhysicianDecisionHandler(uow_factory, audit_writer)
    workflow = workflow_handler.start(clinical_case.id)
    workflow_handler.execute(workflow.id, WorkflowCommand("start_triage", 1, issued_at=NOW))
    workflow_handler.execute(workflow.id, WorkflowCommand("complete_triage", 2, issued_at=NOW))
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "record_ecg",
            3,
            facts_patch={"ecg_available": True, "ecg_quality_acceptable": True},
            issued_at=NOW,
        ),
    )
    workflow_handler.execute(
        workflow.id, WorkflowCommand("request_troponin", 4, due_at=NOW, issued_at=NOW)
    )
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "record_troponin", 5, facts_patch={"troponin_available": True}, issued_at=NOW
        ),
    )
    workflow_handler.execute(workflow.id, WorkflowCommand("select_demo_pathway", 6, issued_at=NOW))

    def record_decision(
        decision_type: PhysicianDecisionType, workflow_version: int
    ) -> tuple[UUID, ActorContext]:
        decision_id = uuid4()
        context = ActorContext.for_actor(actor_id, "physician")
        decision_handler.execute(
            RecordPhysicianDecision(
                decision_id=decision_id,
                clinical_case_id=clinical_case.id,
                workflow_id=workflow.id,
                actor=context,
                decision_type=decision_type,
                decision_status=PhysicianDecisionStatus.ACTIVE,
                reason_code="r0-closure-review",
                evidence_snapshot_reference=f"evidence://snapshot/{decision_type.value}",
                workflow_version=workflow_version,
                aggregate_expected_version=2,
                occurred_at=NOW,
            ),
            recorded_at=NOW,
        )
        return decision_id, context

    pathway_id, pathway_actor = record_decision(PhysicianDecisionType.PATHWAY_ACCEPTED, 7)
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "record_physician_decision",
            7,
            actor_id=actor_id,
            actor_role="physician",
            decision_id=pathway_id,
            case_expected_version=2,
            correlation_id=pathway_actor.correlation_id,
            issued_at=NOW,
        ),
    )
    discharge_id, discharge_actor = record_decision(
        PhysicianDecisionType.DISCHARGE_REVIEW_APPROVED, 8
    )
    workflow_handler.execute(
        workflow.id,
        WorkflowCommand(
            "prepare_discharge_review",
            8,
            actor_id=actor_id,
            actor_role="physician",
            decision_id=discharge_id,
            case_expected_version=2,
            correlation_id=discharge_actor.correlation_id,
            issued_at=NOW,
        ),
    )
    closure_id, closure_actor = record_decision(PhysicianDecisionType.CASE_CLOSURE_APPROVED, 9)
    alert_id = uuid4()
    outcome_id = uuid4()
    with postgres_session_factory() as session:
        session.execute(
            update(ClinicalTaskRecord)
            .where(ClinicalTaskRecord.case_id == clinical_case.id)
            .values(status=TaskStatus.COMPLETED)
        )
        session.add(
            OutcomeRecord(
                id=outcome_id,
                case_id=clinical_case.id,
                summary="Demonstration disposition recorded",
                recorded_at=NOW,
                recorded_by=actor_id,
            )
        )
        session.add(
            AlertRecord(
                id=alert_id,
                case_id=clinical_case.id,
                workflow_id=None,
                workflow_command_id=None,
                workflow_effect=None,
                alert_type="r0-critical-review",
                source="r0-test",
                severity=AlertSeverity.URGENT,
                message="Review before closure",
                status=AlertStatus.ACTIVE,
                raised_at=NOW,
            )
        )
        session.commit()

    close_handler = CloseClinicalCaseHandler(uow_factory, audit_writer)
    rejected_command = CloseClinicalCase(
        command_id=uuid4(),
        clinical_case_id=clinical_case.id,
        workflow_id=workflow.id,
        decision_id=closure_id,
        actor=closure_actor,
        expected_case_version=2,
        expected_workflow_version=9,
        closure_reason="Demonstration closure",
        occurred_at=NOW,
    )
    with pytest.raises(DomainInvariantError, match="critical alerts|guards rejected"):
        close_handler.execute(rejected_command)
    with postgres_session_factory() as session:
        assert session.get(AlertRecord, alert_id).status is AlertStatus.ACTIVE
        assert session.get(AuditLogRecord, rejected_command.command_id).outcome == "rejected"
        assert session.get(ClinicalCaseRecord, clinical_case.id).status is CaseStatus.UNDER_REVIEW

    with postgres_session_factory() as session:
        alert = session.get(AlertRecord, alert_id)
        alert.status = AlertStatus.RESOLVED
        alert.resolved_by = actor_id
        alert.resolved_at = NOW
        alert.resolution_reason = "Reviewed"
        session.commit()
    result = close_handler.execute(
        CloseClinicalCase(
            command_id=uuid4(),
            clinical_case_id=clinical_case.id,
            workflow_id=workflow.id,
            decision_id=closure_id,
            actor=closure_actor,
            expected_case_version=2,
            expected_workflow_version=9,
            closure_reason="Demonstration closure",
            occurred_at=NOW,
        )
    )
    assert not result.duplicate
    with postgres_session_factory() as session:
        assert session.get(ClinicalCaseRecord, clinical_case.id).status is CaseStatus.CLOSED


def test_audit_rows_are_database_immutable(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """PostgreSQL rejects both UPDATE and DELETE against audit history."""
    audit_id = uuid4()
    with postgres_session_factory() as session:
        session.add(
            AuditLogRecord(
                id=audit_id,
                case_id=None,
                aggregate_type="R0Probe",
                aggregate_id=uuid4(),
                action="r0_immutability_probe",
                actor_id=None,
                actor_role="system",
                prior_version=None,
                resulting_version=None,
                reason="verification",
                correlation_id=uuid4(),
                causation_id=None,
                outcome="success",
                occurred_at=NOW,
                payload={},
                source_event_id=None,
            )
        )
        session.commit()

    with postgres_session_factory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(
                text("UPDATE audit_logs SET action='tampered' WHERE id=:id"),
                {"id": audit_id},
            )
            session.commit()
        session.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("DELETE FROM audit_logs WHERE id=:id"), {"id": audit_id})
            session.commit()
