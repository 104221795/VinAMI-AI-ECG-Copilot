"""Efficient SQLAlchemy R8 complete case-workspace projection."""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, aliased

from vinami.alerts.adapters.persistence import AlertRecord
from vinami.alerts.domain.model import AlertStatus
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.clinical_case.ports.case_workspace import CompleteCaseWorkspace
from vinami.ecg.adapters.r3_persistence import (
    ECGAIAnalysisRecord,
    ECGQualityRecord,
    ECGStudyDetailRecord,
    PhysicianECGInterpretationRecord,
)
from vinami.patient.adapters.persistence import EncounterRecord, PatientRecord
from vinami.reasoning.adapters.r5_persistence import (
    ClinicalEvidenceSnapshotRecord,
    ClinicalReasoningDecisionRecord,
    PhysicianClinicalAssessmentRecord,
)
from vinami.reasoning.domain.clinical_evidence import DecisionRecordStatus
from vinami.timeline.adapters.persistence import TimelineEventRecord
from vinami.triage.adapters.persistence import (
    TriageAssessmentRecord,
    TriageStructuredObservationRecord,
    VitalMeasurementRecord,
    VitalObservationSetRecord,
)
from vinami.troponin.adapters.r4_persistence import TroponinAssayRecord, TroponinEvidenceRecord
from vinami.troponin.domain.evidence import calculate_delta
from vinami.workflow.adapters.persistence import ClinicalTaskRecord, ClinicalWorkflowRecord
from vinami.workflow.domain.model import TaskStatus

_ACTIVE_TASKS = (
    TaskStatus.PENDING,
    TaskStatus.ASSIGNED,
    TaskStatus.ACKNOWLEDGED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.OPEN,
    TaskStatus.OVERDUE,
)
_UNRESOLVED_ALERTS = (AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED)


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


class SQLAlchemyCaseWorkspaceReadRepository:
    """Build the R8 response with a fixed query count and no relationship loading."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self, case_id: UUID, visible_locations: tuple[str, ...], now: datetime
    ) -> CompleteCaseWorkspace | None:
        core = self._session.execute(
            select(ClinicalCaseRecord, EncounterRecord, PatientRecord)
            .join(EncounterRecord, EncounterRecord.id == ClinicalCaseRecord.encounter_id)
            .join(PatientRecord, PatientRecord.id == EncounterRecord.patient_id)
            .where(ClinicalCaseRecord.id == case_id)
            .where(EncounterRecord.location.in_(visible_locations))
        ).one_or_none()
        if core is None:
            return None
        case, encounter, patient = core
        triage = self._latest_triage(case_id)
        vitals = self._latest_vitals(case_id)
        ecg = self._latest_ecg(case_id)
        troponin, troponin_token = self._troponin(case_id)
        snapshot = self._latest_snapshot(case_id)
        assessment = self._effective_assessment(case_id)
        decision = self._effective_decision(case_id)
        workflow = self._session.scalar(
            select(ClinicalWorkflowRecord).where(ClinicalWorkflowRecord.case_id == case_id)
        )
        tasks = self._tasks(case_id)
        alerts = self._alerts(case_id)
        timeline = self._timeline(case_id)

        freshness = dict(snapshot.freshness) if snapshot else {}
        missing = (
            tuple(snapshot.missing_evidence)
            if snapshot
            else tuple(
                name
                for name, value in (("triage", triage), ("vitals", vitals), ("ecg", ecg))
                if value is None
            )
            + (() if troponin["result_count"] else ("troponin",))
        )
        stale = tuple(sorted(name for name, state in freshness.items() if state == "stale"))
        technical = tuple(snapshot.technical_conflicts) if snapshot else ()
        if ecg and ecg.get("quality_status") in {
            "limited",
            "poor",
            "insufficient",
            "unsupported",
            "failed",
        }:
            technical = tuple(dict.fromkeys((*technical, "ECG technical quality is limited")))
        evidence_status = (
            "technical_limit"
            if technical
            else "missing"
            if missing
            else "stale"
            if stale
            else "current"
        )
        token_parts = [
            str(case.version),
            str(case.updated_at),
            str(triage["record_version"] if triage else 0),
            str(vitals["record_version"] if vitals else 0),
            str(ecg["record_version"] if ecg else 0),
            troponin_token,
            str(snapshot.record_version if snapshot else 0),
            str(assessment.record_version if assessment else 0),
            str(decision.record_version if decision else 0),
            str(workflow.version if workflow else 0),
            ",".join(f"{item['task_id']}:{item['version']}" for item in tasks),
            ",".join(f"{item['alert_id']}:{item['version']}" for item in alerts),
            str(timeline[0]["timeline_event_id"] if timeline else "none"),
        ]
        update_token = hashlib.sha256("|".join(token_parts).encode()).hexdigest()[:24]
        name = " ".join(part for part in (patient.given_name, patient.family_name) if part) or None
        return CompleteCaseWorkspace(
            case.id,
            encounter.id,
            patient.id,
            patient.identifier_value,
            name,
            patient.age_band,
            patient.sex_at_birth,
            encounter.location,
            str(_value(encounter.status)),
            str(_value(case.status)),
            str(_value(case.priority)),
            case.opening_reason,
            case.opened_at,
            case.updated_at,
            case.version,
            triage,
            vitals,
            ecg,
            troponin,
            self._snapshot(snapshot),
            self._assessment(assessment),
            self._decision(decision),
            self._workflow(workflow),
            tuple(tasks),
            tuple(alerts),
            tuple(timeline),
            evidence_status,
            missing,
            stale,
            technical,
            update_token,
            now,
        )

    def _latest_triage(self, case_id: UUID) -> dict[str, object] | None:
        row = self._session.scalar(
            select(TriageAssessmentRecord)
            .where(TriageAssessmentRecord.clinical_case_id == case_id)
            .order_by(TriageAssessmentRecord.revision_number.desc())
            .limit(1)
        )
        if row is None:
            return None
        observations = self._session.scalars(
            select(TriageStructuredObservationRecord)
            .where(TriageStructuredObservationRecord.triage_assessment_id == row.id)
            .order_by(
                TriageStructuredObservationRecord.category, TriageStructuredObservationRecord.name
            )
        ).all()
        return {
            "assessment_id": row.id,
            "record_version": row.record_version,
            "revision_number": row.revision_number,
            "status": row.status,
            "source": row.source,
            "occurred_at": row.occurred_at,
            "recorded_at": row.recorded_at,
            "chief_complaint": row.chief_complaint,
            "symptom_onset_state": row.symptom_onset_state,
            "symptom_onset_at": row.symptom_onset_at,
            "symptom_description": row.symptom_description,
            "observations": [
                {
                    "category": item.category,
                    "name": item.name,
                    "state": item.state,
                    "note": item.note,
                }
                for item in observations
            ],
        }

    def _latest_vitals(self, case_id: UUID) -> dict[str, object] | None:
        row = self._session.scalar(
            select(VitalObservationSetRecord)
            .where(VitalObservationSetRecord.clinical_case_id == case_id)
            .order_by(
                VitalObservationSetRecord.sequence_number.desc(),
                VitalObservationSetRecord.revision_number.desc(),
            )
            .limit(1)
        )
        if row is None:
            return None
        measurements = self._session.scalars(
            select(VitalMeasurementRecord)
            .where(VitalMeasurementRecord.vital_set_id == row.id)
            .order_by(VitalMeasurementRecord.kind)
        ).all()
        return {
            "vital_set_id": row.id,
            "record_version": row.record_version,
            "sequence_number": row.sequence_number,
            "revision_number": row.revision_number,
            "source": row.source,
            "observed_at": row.observed_at,
            "recorded_at": row.recorded_at,
            "supplemental_oxygen_state": row.supplemental_oxygen_state,
            "level_of_consciousness": row.level_of_consciousness,
            "measurements": [
                {
                    "kind": item.kind,
                    "value": item.value,
                    "unit": item.unit,
                    "quality_status": item.quality_status,
                }
                for item in measurements
            ],
        }

    def _latest_ecg(self, case_id: UUID) -> dict[str, object] | None:
        study = self._session.scalar(
            select(ECGStudyDetailRecord)
            .where(ECGStudyDetailRecord.clinical_case_id == case_id)
            .order_by(
                ECGStudyDetailRecord.acquisition_at.desc(), ECGStudyDetailRecord.study_id.desc()
            )
            .limit(1)
        )
        if study is None:
            return None
        quality = self._session.scalar(
            select(ECGQualityRecord).where(ECGQualityRecord.study_id == study.study_id)
        )
        interpretation = self._session.scalar(
            select(PhysicianECGInterpretationRecord)
            .where(PhysicianECGInterpretationRecord.ecg_study_id == study.study_id)
            .order_by(PhysicianECGInterpretationRecord.revision_number.desc())
            .limit(1)
        )
        analysis = self._session.scalar(
            select(ECGAIAnalysisRecord)
            .where(ECGAIAnalysisRecord.ecg_study_id == study.study_id)
            .order_by(ECGAIAnalysisRecord.requested_at.desc(), ECGAIAnalysisRecord.id.desc())
            .limit(1)
        )
        return {
            "study_id": study.study_id,
            "record_version": study.aggregate_version,
            "study_reference": study.study_reference,
            "source_type": study.source_type,
            "acquisition_at": study.acquisition_at,
            "recorded_at": study.ingestion_at,
            "ingestion_status": study.study_status,
            "quality_status": quality.status if quality else "unknown",
            "quality_reasons": list(quality.reason_codes) if quality else [],
            "analysis": None
            if analysis is None
            else {
                "analysis_id": analysis.id,
                "status": analysis.status,
                "model_name": analysis.model_name,
                "model_version": analysis.model_version,
                "completed_at": analysis.completed_at,
                "warnings": list(analysis.warnings),
                "record_version": analysis.record_version,
            },
            "physician_interpretation": None
            if interpretation is None
            else {
                "interpretation_id": interpretation.id,
                "status": interpretation.interpretation_status,
                "structured_interpretation": interpretation.structured_interpretation,
                "quality_disposition": interpretation.quality_disposition,
                "recorded_at": interpretation.recorded_at,
                "record_version": interpretation.record_version,
                "revision_number": interpretation.revision_number,
            },
        }

    def _troponin(self, case_id: UUID) -> tuple[dict[str, object], str]:
        rows = list(
            self._session.scalars(
                select(TroponinEvidenceRecord)
                .where(TroponinEvidenceRecord.clinical_case_id == case_id)
                .order_by(
                    TroponinEvidenceRecord.specimen_collected_at, TroponinEvidenceRecord.recorded_at
                )
            )
        )
        superseded = {row.supersedes_result_id for row in rows if row.supersedes_result_id}
        effective = [
            row
            for row in rows
            if row.result_id not in superseded
            and row.result_status not in {"cancelled", "entered_in_error"}
        ]
        latest = effective[-1] if effective else None
        assay = self._session.get(TroponinAssayRecord, latest.assay_id) if latest else None
        delta = calculate_delta(effective[-2], effective[-1]) if len(effective) >= 2 else None
        result = (
            None
            if latest is None
            else {
                "result_id": latest.result_id,
                "record_version": latest.record_version,
                "assay_id": latest.assay_id,
                "assay_name": assay.display_name if assay else None,
                "analyte": latest.analyte,
                "value": _decimal(latest.original_value),
                "unit": latest.original_unit,
                "normalized_value": _decimal(latest.normalized_value),
                "normalized_unit": latest.normalized_unit,
                "specimen_collected_at": latest.specimen_collected_at,
                "resulted_at": latest.resulted_at,
                "recorded_at": latest.recorded_at,
                "result_status": latest.result_status,
                "quality_flags": list(latest.quality_flags),
            }
        )
        delta_data = (
            None
            if delta is None
            else {
                "baseline_result_id": delta.baseline_result_id,
                "current_result_id": delta.current_result_id,
                "absolute_change": _decimal(delta.absolute_change),
                "relative_change_percent": _decimal(delta.relative_change_percent),
                "unit": delta.normalized_unit,
                "specimen_interval_seconds": delta.specimen_interval_seconds,
                "compatibility_status": delta.compatibility_status.value,
                "incompatibility_reasons": list(delta.incompatibility_reasons),
                "calculation_policy_version": delta.calculation_policy_version,
                "warning": delta.warning,
            }
        )
        return {
            "result_count": len(effective),
            "latest_result": result,
            "latest_delta": delta_data,
        }, ",".join(f"{row.result_id}:{row.record_version}" for row in effective)

    def _latest_snapshot(self, case_id: UUID) -> ClinicalEvidenceSnapshotRecord | None:
        return self._session.scalar(
            select(ClinicalEvidenceSnapshotRecord)
            .where(ClinicalEvidenceSnapshotRecord.clinical_case_id == case_id)
            .order_by(
                ClinicalEvidenceSnapshotRecord.created_at.desc(),
                ClinicalEvidenceSnapshotRecord.snapshot_id.desc(),
            )
            .limit(1)
        )

    def _effective_assessment(self, case_id: UUID) -> PhysicianClinicalAssessmentRecord | None:
        successor = aliased(PhysicianClinicalAssessmentRecord)
        return self._session.scalar(
            select(PhysicianClinicalAssessmentRecord)
            .where(
                PhysicianClinicalAssessmentRecord.clinical_case_id == case_id,
                ~exists(
                    select(successor.assessment_id).where(
                        successor.corrects_assessment_id
                        == PhysicianClinicalAssessmentRecord.assessment_id
                    )
                ),
            )
            .order_by(PhysicianClinicalAssessmentRecord.revision_number.desc())
            .limit(1)
        )

    def _effective_decision(self, case_id: UUID) -> ClinicalReasoningDecisionRecord | None:
        successor = aliased(ClinicalReasoningDecisionRecord)
        return self._session.scalar(
            select(ClinicalReasoningDecisionRecord)
            .where(
                ClinicalReasoningDecisionRecord.clinical_case_id == case_id,
                ClinicalReasoningDecisionRecord.status != DecisionRecordStatus.REVOCATION.value,
                ~exists(
                    select(successor.decision_id).where(
                        successor.corrects_decision_id
                        == ClinicalReasoningDecisionRecord.decision_id
                    )
                ),
            )
            .order_by(ClinicalReasoningDecisionRecord.revision_number.desc())
            .limit(1)
        )

    def _tasks(self, case_id: UUID) -> list[dict[str, object]]:
        rows = self._session.scalars(
            select(ClinicalTaskRecord)
            .where(
                ClinicalTaskRecord.case_id == case_id, ClinicalTaskRecord.status.in_(_ACTIVE_TASKS)
            )
            .order_by(
                ClinicalTaskRecord.due_at.asc().nulls_last(),
                ClinicalTaskRecord.created_at,
                ClinicalTaskRecord.id,
            )
        ).all()
        return [
            {
                "task_id": row.id,
                "task_type": row.task_type,
                "status": str(_value(row.status)),
                "priority": str(_value(row.priority)),
                "created_at": row.created_at,
                "due_at": row.due_at,
                "overdue_at": row.overdue_at,
                "escalation_level": row.escalation_level,
                "owner_user_id": row.assigned_user_id,
                "owner_team_id": row.assigned_team_id,
                "version": row.version,
            }
            for row in rows
        ]

    def _alerts(self, case_id: UUID) -> list[dict[str, object]]:
        rows = self._session.scalars(
            select(AlertRecord)
            .where(AlertRecord.case_id == case_id, AlertRecord.status.in_(_UNRESOLVED_ALERTS))
            .order_by(AlertRecord.raised_at.desc(), AlertRecord.id.desc())
        ).all()
        return [
            {
                "alert_id": row.id,
                "alert_type": row.alert_type,
                "severity": str(_value(row.severity)),
                "status": str(_value(row.status)),
                "message": row.message,
                "raised_at": row.raised_at,
                "escalation_level": row.escalation_level,
                "version": row.version,
            }
            for row in rows
        ]

    def _timeline(self, case_id: UUID) -> list[dict[str, object]]:
        rows = self._session.scalars(
            select(TimelineEventRecord)
            .where(TimelineEventRecord.case_id == case_id)
            .order_by(TimelineEventRecord.occurred_at.desc(), TimelineEventRecord.id.desc())
            .limit(12)
        ).all()
        return [
            {
                "timeline_event_id": row.id,
                "event_type": row.event_type,
                "title": row.title,
                "occurred_at": row.occurred_at,
                "recorded_at": row.recorded_at,
                "source": row.source,
                "actor_id": row.actor_id,
            }
            for row in rows
        ]

    @staticmethod
    def _snapshot(row: ClinicalEvidenceSnapshotRecord | None) -> dict[str, object] | None:
        return (
            None
            if row is None
            else {
                "snapshot_id": row.snapshot_id,
                "record_version": row.record_version,
                "case_version": row.case_version,
                "created_at": row.created_at,
                "sources": row.sources,
                "freshness": row.freshness,
                "missing_evidence": row.missing_evidence,
                "technical_conflicts": row.technical_conflicts,
            }
        )

    @staticmethod
    def _assessment(row: PhysicianClinicalAssessmentRecord | None) -> dict[str, object] | None:
        return (
            None
            if row is None
            else {
                "assessment_id": row.assessment_id,
                "snapshot_id": row.snapshot_id,
                "record_version": row.record_version,
                "revision_number": row.revision_number,
                "summary": row.summary,
                "supporting_evidence": row.supporting_evidence,
                "contradictory_evidence": row.contradictory_evidence,
                "uncertainty": row.uncertainty,
                "additional_information_required": row.additional_information_required,
                "recorded_at": row.recorded_at,
            }
        )

    @staticmethod
    def _decision(row: ClinicalReasoningDecisionRecord | None) -> dict[str, object] | None:
        return (
            None
            if row is None
            else {
                "decision_id": row.decision_id,
                "snapshot_id": row.snapshot_id,
                "assessment_id": row.assessment_id,
                "record_version": row.record_version,
                "revision_number": row.revision_number,
                "decision_type": row.decision_type,
                "status": row.status,
                "rationale": row.rationale,
                "uncertainty": row.uncertainty,
                "recorded_at": row.recorded_at,
            }
        )

    @staticmethod
    def _workflow(row: ClinicalWorkflowRecord | None) -> dict[str, object] | None:
        return (
            None
            if row is None
            else {
                "workflow_id": row.id,
                "definition_id": row.definition_id,
                "definition_version": row.definition_version,
                "state": str(_value(row.current_state)),
                "last_transition_at": row.last_transition_at,
                "version": row.version,
                "demonstration_notice": row.demonstration_notice,
            }
        )
