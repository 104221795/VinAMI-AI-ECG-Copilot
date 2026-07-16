"""SQLAlchemy adapter for R9 timeline, audit, outcome and research export views."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vinami.audit.adapters.persistence import AuditLogRecord, OutcomeRecord, ResearchExportRecord
from vinami.audit.domain.model import Outcome
from vinami.audit.ports.history import ModelProvenance, Page, ResearchExport
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.ecg.adapters.r3_persistence import ECGAIAnalysisRecord, ECGStudyDetailRecord
from vinami.patient.adapters.persistence import EncounterRecord, PatientRecord
from vinami.reasoning.adapters.r5_persistence import ClinicalEvidenceSnapshotRecord
from vinami.shared.domain import utc_now
from vinami.timeline.adapters.persistence import TimelineEventRecord
from vinami.triage.adapters.persistence import TriageAssessmentRecord, VitalObservationSetRecord
from vinami.troponin.adapters.r4_persistence import TroponinEvidenceRecord


class SQLAlchemyCaseHistoryRepository:
    """Build R9 history and learning read models with explicit SQL queries."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def case_visible(self, case_id: UUID, visible_locations: tuple[str, ...]) -> bool:
        return bool(
            self._session.scalar(
                select(func.count())
                .select_from(ClinicalCaseRecord)
                .join(EncounterRecord, EncounterRecord.id == ClinicalCaseRecord.encounter_id)
                .where(
                    ClinicalCaseRecord.id == case_id,
                    EncounterRecord.location.in_(visible_locations),
                )
            )
        )

    def timeline(
        self,
        case_id: UUID,
        page: int,
        page_size: int,
        event_type: str | None,
        correction_status: str | None,
    ) -> Page:
        where = [TimelineEventRecord.case_id == case_id]
        if event_type:
            where.append(TimelineEventRecord.event_type == event_type)
        if correction_status:
            where.append(TimelineEventRecord.correction_status == correction_status)
        total = int(
            self._session.scalar(
                select(func.count()).select_from(TimelineEventRecord).where(*where)
            )
            or 0
        )
        rows = self._session.scalars(
            select(TimelineEventRecord)
            .where(*where)
            .order_by(TimelineEventRecord.occurred_at.desc(), TimelineEventRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return Page(
            tuple(
                {
                    "timeline_event_id": row.id,
                    "clinical_case_id": row.case_id,
                    "event_type": row.event_type,
                    "title": row.title,
                    "occurred_at": row.occurred_at,
                    "recorded_at": row.recorded_at,
                    "source": row.source,
                    "actor_id": row.actor_id,
                    "correlation_id": row.correlation_id,
                    "causation_id": row.causation_id,
                    "source_record_id": row.source_record_id,
                    "source_record_version": row.source_record_version,
                    "correction_status": row.correction_status,
                    "supersedes_timeline_event_id": row.supersedes_timeline_event_id,
                    "revokes_timeline_event_id": row.revokes_timeline_event_id,
                    "data_classification": row.data_classification,
                }
                for row in rows
            ),
            page,
            page_size,
            total,
        )

    def audit(
        self,
        case_id: UUID,
        page: int,
        page_size: int,
        action: str | None,
        outcome: str | None,
    ) -> Page:
        where = [AuditLogRecord.case_id == case_id]
        if action:
            where.append(AuditLogRecord.action == action)
        if outcome:
            where.append(AuditLogRecord.outcome == outcome)
        total = int(
            self._session.scalar(select(func.count()).select_from(AuditLogRecord).where(*where))
            or 0
        )
        rows = self._session.scalars(
            select(AuditLogRecord)
            .where(*where)
            .order_by(AuditLogRecord.occurred_at.desc(), AuditLogRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return Page(
            tuple(
                {
                    "audit_id": row.id,
                    "actor_id": row.actor_id,
                    "actor_role": row.actor_role,
                    "identity_subject": row.identity_subject,
                    "actor_roles": tuple(row.actor_roles),
                    "applied_permission": row.applied_permission,
                    "identity_provider": row.identity_provider,
                    "authentication_method": row.authentication_method,
                    "session_reference": row.session_reference,
                    "action": row.action,
                    "resource_type": row.aggregate_type,
                    "resource_id": row.aggregate_id,
                    "request_source": row.request_source,
                    "correlation_id": row.correlation_id,
                    "causation_id": row.causation_id,
                    "prior_version": row.prior_version,
                    "resulting_version": row.resulting_version,
                    "outcome": row.outcome,
                    "reason": row.reason,
                    "recorded_at": row.occurred_at,
                    "idempotency_key": row.idempotency_key,
                    "authorization_result": row.authorization_result,
                    "correction_status": row.correction_status,
                    "source_record_version": row.source_record_version,
                }
                for row in rows
            ),
            page,
            page_size,
            total,
        )

    def outcome_history(self, case_id: UUID) -> tuple[Outcome, ...]:
        rows = self._session.scalars(
            select(OutcomeRecord)
            .where(OutcomeRecord.case_id == case_id)
            .order_by(OutcomeRecord.revision_number.desc(), OutcomeRecord.id.desc())
        ).all()
        return tuple(_outcome(row) for row in rows)

    def latest_outcome(self, case_id: UUID) -> Outcome | None:
        row = self._session.scalar(
            select(OutcomeRecord)
            .where(OutcomeRecord.case_id == case_id)
            .order_by(OutcomeRecord.revision_number.desc(), OutcomeRecord.id.desc())
            .limit(1)
        )
        return _outcome(row) if row else None

    def get_outcome(self, outcome_id: UUID) -> Outcome | None:
        row = self._session.get(OutcomeRecord, outcome_id)
        return _outcome(row) if row else None

    def add_outcome(self, outcome: Outcome) -> None:
        self._session.add(
            OutcomeRecord(
                id=outcome.id,
                case_id=outcome.case_id,
                summary=outcome.final_conclusion,
                recorded_at=outcome.recorded_at,
                recorded_by=outcome.recorded_by,
                outcome_type=outcome.outcome_type,
                outcome_timestamp=outcome.outcome_timestamp,
                disposition=outcome.disposition,
                destination=outcome.destination,
                final_conclusion=outcome.final_conclusion,
                cath_lab_review_outcome=outcome.cath_lab_review_outcome,
                intervention_reference=outcome.intervention_reference,
                complications=outcome.complications,
                follow_up_status=outcome.follow_up_status,
                data_completeness=outcome.data_completeness,
                source=outcome.source,
                actor_role=outcome.actor_role,
                uncertainty=outcome.uncertainty,
                unavailable_reason=outcome.unavailable_reason,
                revision_number=outcome.revision_number,
                record_version=outcome.record_version,
                supersedes_outcome_id=outcome.supersedes_outcome_id,
                correction_reason=outcome.correction_reason,
                idempotency_key=outcome.idempotency_key,
                correlation_id=outcome.correlation_id,
                causation_id=outcome.causation_id,
            )
        )

    def model_provenance(self, case_id: UUID) -> tuple[ModelProvenance, ...]:
        rows = self._session.scalars(
            select(ECGAIAnalysisRecord)
            .join(
                ECGStudyDetailRecord,
                ECGStudyDetailRecord.study_id == ECGAIAnalysisRecord.ecg_study_id,
            )
            .where(ECGStudyDetailRecord.clinical_case_id == case_id)
            .order_by(ECGAIAnalysisRecord.requested_at.desc(), ECGAIAnalysisRecord.id.desc())
        ).all()
        return tuple(
            ModelProvenance(
                row.id,
                row.ecg_study_id,
                row.provider_name,
                row.provider_version,
                row.model_name,
                row.model_version,
                row.model_checksum,
                row.threshold_version,
                row.preprocessing_version,
                row.label_mapping_version,
                row.completed_at,
                row.quality_status,
                row.input_artifact_id,
                row.input_artifact_checksum,
                row.explanation_artifact_id,
                row.explanation_status,
                row.synthetic,
                row.status,
                tuple(row.warnings),
                row.record_version,
            )
            for row in rows
        )

    def build_research_export(
        self,
        case_ids: tuple[UUID, ...],
        requested_by: UUID,
        requested_by_role: str,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> ResearchExport:
        cases = self._session.execute(
            select(ClinicalCaseRecord, EncounterRecord, PatientRecord)
            .join(EncounterRecord, EncounterRecord.id == ClinicalCaseRecord.encounter_id)
            .join(PatientRecord, PatientRecord.id == EncounterRecord.patient_id)
            .where(ClinicalCaseRecord.id.in_(case_ids))
            .order_by(ClinicalCaseRecord.opened_at, ClinicalCaseRecord.id)
        ).all()
        payload_cases: list[dict[str, object]] = []
        for case, encounter, patient in cases:
            research_id = _research_id(case.id, patient.id)
            payload_cases.append(
                {
                    "research_case_id": research_id,
                    "clinical_case_id_hash": _hash_value(str(case.id)),
                    "encounter_id_hash": _hash_value(str(encounter.id)),
                    "case_status": str(getattr(case.status, "value", case.status)),
                    "case_priority": str(getattr(case.priority, "value", case.priority)),
                    "opened_at": case.opened_at.isoformat(),
                    "case_version": case.version,
                    "evidence": self._export_evidence(case.id),
                    "outcomes": [_outcome_document(item) for item in self.outcome_history(case.id)],
                    "model_provenance": [
                        _provenance_document(item) for item in self.model_provenance(case.id)
                    ],
                    "missing_data_semantics": "missing fields are omitted only when no persisted source record exists",
                }
            )
        now = utc_now()
        content_json = {
            "schema_version": "vinami.research_export.r9.v1",
            "requested_at": now.isoformat(),
            "pseudonymization": {
                "method": "sha256 clinical-case and patient scoped research identifiers",
                "direct_identifiers_excluded": True,
            },
            "cases": payload_cases,
        }
        normalized = json.dumps(content_json, sort_keys=True, default=str, separators=(",", ":"))
        checksum = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        content_csv = _export_csv(payload_cases)
        return ResearchExport(
            export_id=_uuid_from_hash(f"{requested_by}:{idempotency_key}:{checksum}"),
            status="completed",
            schema_version="vinami.research_export.r9.v1",
            requested_by=requested_by,
            requested_by_role=requested_by_role,
            requested_at=now,
            completed_at=now,
            case_ids=tuple(case.id for case, _, _ in cases),
            filters={"case_ids": [str(item) for item in case_ids]},
            row_count=len(payload_cases),
            pseudonymization_method="sha256_case_patient_research_id",
            checksum_sha256=checksum,
            content_json=content_json,
            content_csv=content_csv,
            correlation_id=correlation_id,
            metadata={
                "idempotency_key": idempotency_key,
                "model_outputs_are_scores_not_probabilities": True,
            },
        )

    def add_research_export(self, export: ResearchExport, idempotency_key: str) -> None:
        self._session.add(
            ResearchExportRecord(
                export_id=export.export_id,
                status=export.status,
                schema_version=export.schema_version,
                requested_by=export.requested_by,
                requested_by_role=export.requested_by_role,
                requested_at=export.requested_at,
                completed_at=export.completed_at,
                case_ids=[str(item) for item in export.case_ids],
                filters=export.filters,
                row_count=export.row_count,
                pseudonymization_method=export.pseudonymization_method,
                checksum_sha256=export.checksum_sha256,
                content_json=export.content_json,
                content_csv=export.content_csv,
                idempotency_key=idempotency_key,
                correlation_id=export.correlation_id,
                metadata_document=export.metadata,
            )
        )

    def get_research_export(self, export_id: UUID) -> ResearchExport | None:
        row = self._session.get(ResearchExportRecord, export_id)
        return _research_export(row) if row else None

    def find_research_export(self, actor_id: UUID, idempotency_key: str) -> ResearchExport | None:
        row = self._session.scalar(
            select(ResearchExportRecord).where(
                ResearchExportRecord.requested_by == actor_id,
                ResearchExportRecord.idempotency_key == idempotency_key,
            )
        )
        return _research_export(row) if row else None

    def _export_evidence(self, case_id: UUID) -> dict[str, object]:
        triage_count = int(
            self._session.scalar(
                select(func.count()).select_from(TriageAssessmentRecord).where(
                    TriageAssessmentRecord.clinical_case_id == case_id
                )
            )
            or 0
        )
        vital_count = int(
            self._session.scalar(
                select(func.count()).select_from(VitalObservationSetRecord).where(
                    VitalObservationSetRecord.clinical_case_id == case_id
                )
            )
            or 0
        )
        ecg_count = int(
            self._session.scalar(
                select(func.count()).select_from(ECGStudyDetailRecord).where(
                    ECGStudyDetailRecord.clinical_case_id == case_id
                )
            )
            or 0
        )
        troponin_rows = self._session.scalars(
            select(TroponinEvidenceRecord)
            .where(TroponinEvidenceRecord.clinical_case_id == case_id)
            .order_by(TroponinEvidenceRecord.specimen_collected_at, TroponinEvidenceRecord.result_id)
        ).all()
        snapshot = self._session.scalar(
            select(ClinicalEvidenceSnapshotRecord)
            .where(ClinicalEvidenceSnapshotRecord.clinical_case_id == case_id)
            .order_by(ClinicalEvidenceSnapshotRecord.created_at.desc())
            .limit(1)
        )
        return {
            "triage_revision_count": triage_count,
            "vital_revision_count": vital_count,
            "ecg_study_count": ecg_count,
            "troponin_results": [
                {
                    "result_id_hash": _hash_value(str(row.result_id)),
                    "source_revision": row.source_revision,
                    "result_status": row.result_status,
                    "specimen_collected_at": row.specimen_collected_at.isoformat(),
                    "resulted_at": row.resulted_at.isoformat(),
                    "record_version": row.record_version,
                    "quality_flags": list(row.quality_flags),
                }
                for row in troponin_rows
            ],
            "latest_snapshot": None
            if snapshot is None
            else {
                "snapshot_id_hash": _hash_value(str(snapshot.snapshot_id)),
                "missing_evidence": list(snapshot.missing_evidence),
                "freshness": dict(snapshot.freshness),
                "technical_conflicts": list(snapshot.technical_conflicts),
                "record_version": snapshot.record_version,
            },
        }


def _outcome(row: OutcomeRecord) -> Outcome:
    return Outcome(
        id=row.id,
        case_id=row.case_id,
        outcome_type=row.outcome_type,
        outcome_timestamp=row.outcome_timestamp or row.recorded_at,
        final_conclusion=row.final_conclusion or row.summary,
        recorded_at=row.recorded_at,
        recorded_by=row.recorded_by or UUID(int=0),
        actor_role=row.actor_role or "unknown",
        revision_number=row.revision_number,
        record_version=row.record_version,
        disposition=row.disposition,
        destination=row.destination,
        cath_lab_review_outcome=row.cath_lab_review_outcome,
        intervention_reference=row.intervention_reference,
        complications=row.complications,
        follow_up_status=row.follow_up_status,
        data_completeness=row.data_completeness,
        source=row.source,
        uncertainty=row.uncertainty,
        unavailable_reason=row.unavailable_reason,
        supersedes_outcome_id=row.supersedes_outcome_id,
        correction_reason=row.correction_reason,
        idempotency_key=row.idempotency_key,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
    )


def _research_export(row: ResearchExportRecord) -> ResearchExport:
    return ResearchExport(
        export_id=row.export_id,
        status=row.status,
        schema_version=row.schema_version,
        requested_by=row.requested_by,
        requested_by_role=row.requested_by_role,
        requested_at=row.requested_at,
        completed_at=row.completed_at,
        case_ids=tuple(UUID(value) for value in row.case_ids),
        filters=dict(row.filters),
        row_count=row.row_count,
        pseudonymization_method=row.pseudonymization_method,
        checksum_sha256=row.checksum_sha256,
        content_json=dict(row.content_json),
        content_csv=row.content_csv,
        correlation_id=row.correlation_id,
        metadata=dict(row.metadata_document),
    )


def _outcome_document(outcome: Outcome) -> dict[str, object]:
    return {
        "outcome_id_hash": _hash_value(str(outcome.id)),
        "outcome_type": outcome.outcome_type,
        "outcome_timestamp": outcome.outcome_timestamp.isoformat(),
        "final_conclusion": outcome.final_conclusion,
        "revision_number": outcome.revision_number,
        "record_version": outcome.record_version,
        "supersedes_outcome_id_hash": (
            _hash_value(str(outcome.supersedes_outcome_id))
            if outcome.supersedes_outcome_id
            else None
        ),
        "data_completeness": outcome.data_completeness,
        "source": outcome.source,
        "uncertainty": outcome.uncertainty,
        "unavailable_reason": outcome.unavailable_reason,
    }


def _provenance_document(value: ModelProvenance) -> dict[str, object]:
    return {
        "analysis_id_hash": _hash_value(str(value.analysis_id)),
        "study_id_hash": _hash_value(str(value.study_id)),
        "provider_name": value.provider_name,
        "provider_version": value.provider_version,
        "model_name": value.model_name,
        "model_version": value.model_version,
        "model_checksum": value.model_checksum,
        "threshold_version": value.threshold_version,
        "executed_at": value.executed_at.isoformat() if value.executed_at else None,
        "input_quality": value.input_quality,
        "explanation_status": value.explanation_status,
        "synthetic": value.synthetic,
        "status": value.status,
        "record_version": value.record_version,
        "model_outputs_are_scores_not_probabilities": True,
    }


def _export_csv(cases: list[dict[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "research_case_id",
            "case_status",
            "case_priority",
            "opened_at",
            "outcome_revision_count",
            "model_provenance_count",
        ],
    )
    writer.writeheader()
    for item in cases:
        outcomes = item["outcomes"] if isinstance(item["outcomes"], list) else []
        model_provenance = (
            item["model_provenance"] if isinstance(item["model_provenance"], list) else []
        )
        writer.writerow(
            {
                "research_case_id": item["research_case_id"],
                "case_status": item["case_status"],
                "case_priority": item["case_priority"],
                "opened_at": item["opened_at"],
                "outcome_revision_count": len(outcomes),
                "model_provenance_count": len(model_provenance),
            }
        )
    return buffer.getvalue()


def _research_id(case_id: UUID, patient_id: UUID) -> str:
    return f"VINAMI-R9-{_hash_value(f'{case_id}:{patient_id}')[:16].upper()}"


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _uuid_from_hash(value: str) -> UUID:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return UUID(bytes=digest[:16])
