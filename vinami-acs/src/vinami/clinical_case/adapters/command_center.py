"""Efficient SQLAlchemy R7 Command Center projection."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, case, cast, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from vinami.alerts.adapters.persistence import AlertRecord
from vinami.alerts.domain.model import AlertSeverity, AlertStatus
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.clinical_case.domain.model import CaseStatus, ClinicalPriority
from vinami.clinical_case.ports.command_center import (
    CommandCenterAlert,
    CommandCenterCase,
    CommandCenterQuery,
    CommandCenterTask,
)
from vinami.ecg.adapters.r3_persistence import ECGQualityRecord, ECGStudyDetailRecord
from vinami.patient.adapters.persistence import EncounterRecord, PatientRecord
from vinami.reasoning.adapters.r5_persistence import (
    ClinicalEvidenceSnapshotRecord,
    ClinicalReasoningDecisionRecord,
)
from vinami.triage.adapters.persistence import TriageAssessmentRecord, VitalObservationSetRecord
from vinami.troponin.adapters.r4_persistence import TroponinEvidenceRecord
from vinami.workflow.adapters.persistence import (
    ClinicalTaskRecord,
    ClinicalWorkflowRecord,
)
from vinami.workflow.domain.model import TaskPriority, TaskStatus

_ACTIVE_TASKS = (
    TaskStatus.PENDING,
    TaskStatus.ASSIGNED,
    TaskStatus.ACKNOWLEDGED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.OPEN,
    TaskStatus.OVERDUE,
)


class SQLAlchemyCommandCenterReadRepository:
    """Build one page with a fixed number of SQL statements and no row-level loading."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_active(self, query: CommandCenterQuery) -> tuple[list[CommandCenterCase], int]:
        task_agg = self._task_aggregate()
        alert_agg = self._alert_aggregate()
        snapshot = self._latest_snapshot()
        decision = self._latest_effective_decision()
        ecg = self._latest_ecg()
        triage = self._latest_timestamp(
            TriageAssessmentRecord.clinical_case_id,
            TriageAssessmentRecord.recorded_at,
            "triage_at",
        )
        vitals = self._latest_timestamp(
            VitalObservationSetRecord.clinical_case_id,
            VitalObservationSetRecord.observed_at,
            "vitals_at",
        )
        troponin = self._latest_timestamp(
            TroponinEvidenceRecord.clinical_case_id,
            TroponinEvidenceRecord.resulted_at,
            "troponin_at",
            TroponinEvidenceRecord.result_status != "entered_in_error",
        )

        zero = 0
        active_count = func.coalesce(task_agg.c.active_count, zero)
        overdue_count = func.coalesce(task_agg.c.overdue_count, zero)
        alert_count = func.coalesce(alert_agg.c.unresolved_count, zero)
        urgent_alert_count = func.coalesce(alert_agg.c.urgent_count, zero)
        task_escalation = func.coalesce(task_agg.c.max_escalation, zero)
        alert_escalation = func.coalesce(alert_agg.c.max_escalation, zero)
        operational_priority = case(
            (
                or_(
                    urgent_alert_count > 0,
                    task_escalation > 0,
                    alert_escalation > 0,
                    ClinicalCaseRecord.priority == ClinicalPriority.CRITICAL,
                ),
                "critical",
            ),
            (
                or_(
                    overdue_count > 0,
                    func.coalesce(task_agg.c.urgent_count, zero) > 0,
                    alert_count > 0,
                    ClinicalCaseRecord.priority == ClinicalPriority.URGENT,
                ),
                "urgent",
            ),
            else_="routine",
        ).label("operational_priority")
        priority_reason = case(
            (urgent_alert_count > 0, "Unresolved urgent operational alert"),
            (or_(task_escalation > 0, alert_escalation > 0), "Persisted R6 escalation"),
            (overdue_count > 0, "Persisted overdue clinical task"),
            (
                func.coalesce(task_agg.c.urgent_count, zero) > 0,
                "Urgent active clinical task",
            ),
            (alert_count > 0, "Unresolved operational alert"),
            (
                ClinicalCaseRecord.priority == ClinicalPriority.CRITICAL,
                "Human-recorded critical case priority",
            ),
            (
                ClinicalCaseRecord.priority == ClinicalPriority.URGENT,
                "Human-recorded urgent case priority",
            ),
            else_="Routine operational review",
        ).label("priority_reason")

        stale_before = query.now - timedelta(hours=24)
        technical_limit = or_(
            ecg.c.quality_status.in_(("limited", "unusable")),
            func.coalesce(func.jsonb_array_length(snapshot.c.technical_conflicts), 0) > 0,
        )
        evidence_missing = or_(
            triage.c.triage_at.is_(None),
            vitals.c.vitals_at.is_(None),
            ecg.c.acquisition_at.is_(None),
            troponin.c.troponin_at.is_(None),
            func.coalesce(func.jsonb_array_length(snapshot.c.missing_evidence), 0) > 0,
        )
        evidence_stale = or_(
            triage.c.triage_at < stale_before,
            vitals.c.vitals_at < stale_before,
            ecg.c.acquisition_at < stale_before,
            troponin.c.troponin_at < stale_before,
        )
        evidence_status = case(
            (technical_limit, "technical_limit"),
            (evidence_missing, "missing"),
            (evidence_stale, "stale"),
            else_="current",
        ).label("evidence_status")
        latest_activity = func.greatest(
            ClinicalCaseRecord.updated_at,
            func.coalesce(ClinicalWorkflowRecord.last_transition_at, ClinicalCaseRecord.opened_at),
            func.coalesce(snapshot.c.snapshot_created_at, ClinicalCaseRecord.opened_at),
            func.coalesce(decision.c.decision_recorded_at, ClinicalCaseRecord.opened_at),
            func.coalesce(task_agg.c.last_task_activity, ClinicalCaseRecord.opened_at),
            func.coalesce(alert_agg.c.last_alert_activity, ClinicalCaseRecord.opened_at),
        ).label("latest_activity_at")

        statement = (
            select(
                ClinicalCaseRecord.id.label("case_id"),
                ClinicalCaseRecord.encounter_id,
                ClinicalCaseRecord.status.label("case_status"),
                ClinicalCaseRecord.priority.label("case_priority"),
                ClinicalCaseRecord.version.label("case_version"),
                ClinicalCaseRecord.opened_at,
                EncounterRecord.patient_id,
                EncounterRecord.location,
                PatientRecord.identifier_value.label("patient_reference"),
                PatientRecord.age_band,
                PatientRecord.sex_at_birth,
                ClinicalWorkflowRecord.id.label("workflow_id"),
                ClinicalWorkflowRecord.current_state.label("workflow_state"),
                ClinicalWorkflowRecord.version.label("workflow_version"),
                operational_priority,
                priority_reason,
                active_count.label("active_task_count"),
                overdue_count.label("overdue_task_count"),
                alert_count.label("unresolved_alert_count"),
                task_agg.c.next_due_at,
                task_agg.c.oldest_overdue_at,
                task_agg.c.owner_user_id,
                task_agg.c.owner_team_id,
                snapshot.c.snapshot_id,
                snapshot.c.snapshot_created_at,
                snapshot.c.freshness,
                snapshot.c.missing_evidence,
                snapshot.c.technical_conflicts,
                evidence_status,
                decision.c.decision_id,
                decision.c.decision_type,
                decision.c.decision_rationale,
                decision.c.decision_recorded_at,
                latest_activity,
                func.coalesce(task_agg.c.max_task_version, 0).label("max_task_version"),
                func.coalesce(alert_agg.c.max_alert_version, 0).label("max_alert_version"),
                triage.c.triage_at,
                vitals.c.vitals_at,
                ecg.c.acquisition_at.label("ecg_at"),
                troponin.c.troponin_at,
                ecg.c.quality_status.label("ecg_quality_status"),
            )
            .join(EncounterRecord, EncounterRecord.id == ClinicalCaseRecord.encounter_id)
            .join(PatientRecord, PatientRecord.id == EncounterRecord.patient_id)
            .outerjoin(
                ClinicalWorkflowRecord, ClinicalWorkflowRecord.case_id == ClinicalCaseRecord.id
            )
            .outerjoin(task_agg, task_agg.c.case_id == ClinicalCaseRecord.id)
            .outerjoin(alert_agg, alert_agg.c.case_id == ClinicalCaseRecord.id)
            .outerjoin(snapshot, snapshot.c.clinical_case_id == ClinicalCaseRecord.id)
            .outerjoin(decision, decision.c.clinical_case_id == ClinicalCaseRecord.id)
            .outerjoin(triage, triage.c.clinical_case_id == ClinicalCaseRecord.id)
            .outerjoin(vitals, vitals.c.clinical_case_id == ClinicalCaseRecord.id)
            .outerjoin(ecg, ecg.c.clinical_case_id == ClinicalCaseRecord.id)
            .outerjoin(troponin, troponin.c.clinical_case_id == ClinicalCaseRecord.id)
            .where(ClinicalCaseRecord.status != CaseStatus.CLOSED)
        )
        if query.visible_locations:
            statement = statement.where(EncounterRecord.location.in_(query.visible_locations))
        if query.priority:
            statement = statement.where(operational_priority == query.priority)
        if query.workflow_state:
            statement = statement.where(
                ClinicalWorkflowRecord.current_state == query.workflow_state
            )
        if query.overdue is not None:
            statement = statement.where(overdue_count > 0 if query.overdue else overdue_count == 0)
        if query.alert_status == "unresolved":
            statement = statement.where(alert_count > 0)
        elif query.alert_status == "none":
            statement = statement.where(alert_count == 0)
        elif query.alert_status in {"active", "acknowledged"}:
            column = (
                alert_agg.c.active_count
                if query.alert_status == "active"
                else alert_agg.c.acknowledged_count
            )
            statement = statement.where(func.coalesce(column, 0) > 0)
        if query.evidence_status:
            statement = statement.where(evidence_status == query.evidence_status)
        if query.owner_id:
            statement = statement.where(
                or_(
                    task_agg.c.owner_user_id == str(query.owner_id),
                    task_agg.c.owner_team_id == str(query.owner_id),
                )
            )

        total = int(
            self._session.scalar(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
            or 0
        )
        statement = self._ordered(statement, query, operational_priority, latest_activity)
        rows = (
            self._session.execute(
                statement.offset((query.page - 1) * query.page_size).limit(query.page_size)
            )
            .mappings()
            .all()
        )
        case_ids = [row["case_id"] for row in rows]
        tasks = self._tasks(case_ids)
        alerts = self._alerts(case_ids)
        return [
            self._map(row, tasks[row["case_id"]], alerts[row["case_id"]], query) for row in rows
        ], total

    @staticmethod
    def _task_aggregate() -> Any:
        changed_at = func.greatest(
            ClinicalTaskRecord.created_at,
            func.coalesce(ClinicalTaskRecord.acknowledged_at, ClinicalTaskRecord.created_at),
            func.coalesce(ClinicalTaskRecord.started_at, ClinicalTaskRecord.created_at),
            func.coalesce(ClinicalTaskRecord.completed_at, ClinicalTaskRecord.created_at),
            func.coalesce(ClinicalTaskRecord.cancelled_at, ClinicalTaskRecord.created_at),
            func.coalesce(ClinicalTaskRecord.overdue_at, ClinicalTaskRecord.created_at),
        )
        return (
            select(
                ClinicalTaskRecord.case_id,
                func.count()
                .filter(ClinicalTaskRecord.status.in_(_ACTIVE_TASKS))
                .label("active_count"),
                func.count()
                .filter(ClinicalTaskRecord.status == TaskStatus.OVERDUE)
                .label("overdue_count"),
                func.count()
                .filter(
                    and_(
                        ClinicalTaskRecord.status.in_(_ACTIVE_TASKS),
                        ClinicalTaskRecord.priority == TaskPriority.URGENT,
                    )
                )
                .label("urgent_count"),
                func.min(ClinicalTaskRecord.due_at)
                .filter(ClinicalTaskRecord.status.in_(_ACTIVE_TASKS))
                .label("next_due_at"),
                func.min(ClinicalTaskRecord.overdue_at)
                .filter(ClinicalTaskRecord.status == TaskStatus.OVERDUE)
                .label("oldest_overdue_at"),
                func.max(cast(ClinicalTaskRecord.assigned_user_id, String))
                .filter(ClinicalTaskRecord.status.in_(_ACTIVE_TASKS))
                .label("owner_user_id"),
                func.max(cast(ClinicalTaskRecord.assigned_team_id, String))
                .filter(ClinicalTaskRecord.status.in_(_ACTIVE_TASKS))
                .label("owner_team_id"),
                func.max(ClinicalTaskRecord.escalation_level).label("max_escalation"),
                func.max(ClinicalTaskRecord.version).label("max_task_version"),
                func.max(changed_at).label("last_task_activity"),
            )
            .group_by(ClinicalTaskRecord.case_id)
            .subquery("r7_task_aggregate")
        )

    @staticmethod
    def _alert_aggregate() -> Any:
        unresolved = AlertRecord.status != AlertStatus.RESOLVED
        changed_at = func.greatest(
            AlertRecord.raised_at,
            func.coalesce(AlertRecord.acknowledged_at, AlertRecord.raised_at),
            func.coalesce(AlertRecord.resolved_at, AlertRecord.raised_at),
        )
        return (
            select(
                AlertRecord.case_id,
                func.count().filter(unresolved).label("unresolved_count"),
                func.count().filter(AlertRecord.status == AlertStatus.ACTIVE).label("active_count"),
                func.count()
                .filter(AlertRecord.status == AlertStatus.ACKNOWLEDGED)
                .label("acknowledged_count"),
                func.count()
                .filter(and_(unresolved, AlertRecord.severity == AlertSeverity.URGENT))
                .label("urgent_count"),
                func.max(AlertRecord.escalation_level).filter(unresolved).label("max_escalation"),
                func.max(AlertRecord.version).label("max_alert_version"),
                func.max(changed_at).label("last_alert_activity"),
            )
            .group_by(AlertRecord.case_id)
            .subquery("r7_alert_aggregate")
        )

    @staticmethod
    def _latest_snapshot() -> Any:
        ranked = select(
            ClinicalEvidenceSnapshotRecord.snapshot_id,
            ClinicalEvidenceSnapshotRecord.clinical_case_id,
            ClinicalEvidenceSnapshotRecord.record_version,
            ClinicalEvidenceSnapshotRecord.created_at.label("snapshot_created_at"),
            ClinicalEvidenceSnapshotRecord.freshness,
            ClinicalEvidenceSnapshotRecord.missing_evidence,
            ClinicalEvidenceSnapshotRecord.technical_conflicts,
            func.row_number()
            .over(
                partition_by=ClinicalEvidenceSnapshotRecord.clinical_case_id,
                order_by=(
                    ClinicalEvidenceSnapshotRecord.created_at.desc(),
                    ClinicalEvidenceSnapshotRecord.snapshot_id.desc(),
                ),
            )
            .label("rank"),
        ).subquery()
        return select(ranked).where(ranked.c.rank == 1).subquery("r7_latest_snapshot")

    @staticmethod
    def _latest_effective_decision() -> Any:
        successor = aliased(ClinicalReasoningDecisionRecord)
        candidates = (
            select(
                ClinicalReasoningDecisionRecord.decision_id,
                ClinicalReasoningDecisionRecord.clinical_case_id,
                ClinicalReasoningDecisionRecord.decision_type,
                ClinicalReasoningDecisionRecord.rationale.label("decision_rationale"),
                ClinicalReasoningDecisionRecord.recorded_at.label("decision_recorded_at"),
                func.row_number()
                .over(
                    partition_by=ClinicalReasoningDecisionRecord.clinical_case_id,
                    order_by=(
                        ClinicalReasoningDecisionRecord.revision_number.desc(),
                        ClinicalReasoningDecisionRecord.decision_id.desc(),
                    ),
                )
                .label("rank"),
            )
            .where(
                ClinicalReasoningDecisionRecord.status != "revocation",
                ~exists().where(
                    successor.corrects_decision_id == ClinicalReasoningDecisionRecord.decision_id
                ),
            )
            .subquery()
        )
        return select(candidates).where(candidates.c.rank == 1).subquery("r7_effective_decision")

    @staticmethod
    def _latest_ecg() -> Any:
        ranked = (
            select(
                ECGStudyDetailRecord.clinical_case_id,
                ECGStudyDetailRecord.acquisition_at,
                ECGQualityRecord.status.label("quality_status"),
                func.row_number()
                .over(
                    partition_by=ECGStudyDetailRecord.clinical_case_id,
                    order_by=(
                        ECGStudyDetailRecord.acquisition_at.desc(),
                        ECGStudyDetailRecord.study_id.desc(),
                    ),
                )
                .label("rank"),
            )
            .outerjoin(ECGQualityRecord, ECGQualityRecord.study_id == ECGStudyDetailRecord.study_id)
            .subquery()
        )
        return select(ranked).where(ranked.c.rank == 1).subquery("r7_latest_ecg")

    @staticmethod
    def _latest_timestamp(
        case_column: Any, timestamp_column: Any, label: str, *filters: Any
    ) -> Any:
        return (
            select(case_column.label("clinical_case_id"), func.max(timestamp_column).label(label))
            .where(*filters)
            .group_by(case_column)
            .subquery(f"r7_latest_{label}")
        )

    @staticmethod
    def _ordered(statement: Any, query: CommandCenterQuery, priority: Any, activity: Any) -> Any:
        priority_rank = case((priority == "critical", 3), (priority == "urgent", 2), else_=1)
        values = {
            "priority": priority_rank,
            "opened_at": ClinicalCaseRecord.opened_at,
            "next_due_at": func.coalesce(
                statement.selected_columns.next_due_at, query.now + timedelta(days=36500)
            ),
            "latest_activity": activity,
        }
        selected = values[query.sort]
        ordered = selected.asc() if query.direction == "asc" else selected.desc()
        return statement.order_by(
            ordered, ClinicalCaseRecord.opened_at.desc(), ClinicalCaseRecord.id.asc()
        )

    def _tasks(self, case_ids: list[UUID]) -> defaultdict[UUID, list[CommandCenterTask]]:
        result: defaultdict[UUID, list[CommandCenterTask]] = defaultdict(list)
        if not case_ids:
            return result
        rows = self._session.scalars(
            select(ClinicalTaskRecord)
            .where(
                ClinicalTaskRecord.case_id.in_(case_ids),
                ClinicalTaskRecord.status.in_(_ACTIVE_TASKS),
            )
            .order_by(
                ClinicalTaskRecord.case_id,
                ClinicalTaskRecord.due_at.asc().nullslast(),
                ClinicalTaskRecord.created_at,
            )
        ).all()
        for row in rows:
            result[row.case_id].append(
                CommandCenterTask(
                    row.id,
                    row.task_type,
                    row.status.value,
                    row.priority.value,
                    row.due_at,
                    row.overdue_at,
                    row.escalation_level,
                    row.assigned_user_id,
                    row.assigned_team_id,
                )
            )
        return result

    def _alerts(self, case_ids: list[UUID]) -> defaultdict[UUID, list[CommandCenterAlert]]:
        result: defaultdict[UUID, list[CommandCenterAlert]] = defaultdict(list)
        if not case_ids:
            return result
        rows = self._session.scalars(
            select(AlertRecord)
            .where(AlertRecord.case_id.in_(case_ids), AlertRecord.status != AlertStatus.RESOLVED)
            .order_by(AlertRecord.case_id, AlertRecord.raised_at.desc(), AlertRecord.id)
        ).all()
        for row in rows:
            result[row.case_id].append(
                CommandCenterAlert(
                    row.id,
                    row.alert_type,
                    row.severity.value,
                    row.status.value,
                    row.raised_at,
                    row.escalation_level,
                )
            )
        return result

    @staticmethod
    def _map(
        row: Any,
        tasks: list[CommandCenterTask],
        alerts: list[CommandCenterAlert],
        query: CommandCenterQuery,
    ) -> CommandCenterCase:
        freshness = dict(row["freshness"] or {})
        timestamps = {
            "triage": row["triage_at"],
            "vitals": row["vitals_at"],
            "ecg": row["ecg_at"],
            "troponin": row["troponin_at"],
        }
        stale_before = query.now - timedelta(hours=24)
        for name, timestamp in timestamps.items():
            freshness[name] = (
                "missing"
                if timestamp is None
                else ("stale" if timestamp < stale_before else "current")
            )
        if row["ecg_quality_status"] in {"limited", "unusable"}:
            freshness["ecg"] = "technical_limit"
        missing = set(row["missing_evidence"] or [])
        missing.update(name for name, timestamp in timestamps.items() if timestamp is None)
        technical = tuple(row["technical_conflicts"] or [])
        if row["ecg_quality_status"] in {"limited", "unusable"}:
            technical = (*technical, f"Latest ECG quality is {row['ecg_quality_status']}")
        owner_user = UUID(row["owner_user_id"]) if row["owner_user_id"] else None
        owner_team = UUID(row["owner_team_id"]) if row["owner_team_id"] else None
        token = ":".join(
            str(value or 0)
            for value in (
                row["case_version"],
                row["workflow_version"],
                row["max_task_version"],
                row["max_alert_version"],
                row["snapshot_id"],
                row["decision_id"],
            )
        )
        return CommandCenterCase(
            row["case_id"],
            row["encounter_id"],
            row["patient_id"],
            row["patient_reference"],
            row["age_band"],
            row["sex_at_birth"],
            row["location"],
            row["case_status"].value,
            row["case_priority"].value,
            row["case_version"],
            row["opened_at"],
            row["workflow_id"],
            row["workflow_state"].value if row["workflow_state"] else None,
            row["workflow_version"],
            row["operational_priority"],
            row["priority_reason"],
            row["active_task_count"],
            row["overdue_task_count"],
            row["unresolved_alert_count"],
            row["next_due_at"],
            row["oldest_overdue_at"],
            owner_user,
            owner_team,
            row["snapshot_id"],
            row["snapshot_created_at"],
            row["evidence_status"],
            freshness,
            tuple(sorted(missing)),
            technical,
            row["decision_id"],
            row["decision_type"],
            row["decision_rationale"],
            row["decision_recorded_at"],
            row["latest_activity_at"],
            token,
            tuple(tasks),
            tuple(alerts),
        )
