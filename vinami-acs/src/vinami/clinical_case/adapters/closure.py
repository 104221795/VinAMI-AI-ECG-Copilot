"""SQLAlchemy query adapter for safe case-closure evidence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vinami.alerts.adapters.persistence import AlertRecord
from vinami.alerts.domain.model import AlertSeverity, AlertStatus
from vinami.audit.adapters.persistence import OutcomeRecord
from vinami.clinical_case.ports.closure import CaseClosureEvidence
from vinami.workflow.adapters.persistence import ClinicalTaskRecord
from vinami.workflow.domain.model import TaskStatus


class SQLAlchemyCaseClosureEvidenceRepository:
    """Read current safety facts inside the same transaction as case closure."""

    def __init__(self, session: Session) -> None:
        """Bind closure evidence reads to the command transaction."""
        self._session = session

    def for_case(self, case_id: UUID) -> CaseClosureEvidence:
        """Count unresolved urgent alerts/tasks and resolve the required outcome reference."""
        alerts = self._session.scalar(
            select(func.count())
            .select_from(AlertRecord)
            .where(
                AlertRecord.case_id == case_id,
                AlertRecord.severity == AlertSeverity.URGENT,
                AlertRecord.status != AlertStatus.RESOLVED,
            )
        )
        tasks = self._session.scalar(
            select(func.count())
            .select_from(ClinicalTaskRecord)
            .where(
                ClinicalTaskRecord.case_id == case_id,
                ClinicalTaskRecord.status == TaskStatus.OPEN,
            )
        )
        outcome_id = self._session.scalar(
            select(OutcomeRecord.id)
            .where(OutcomeRecord.case_id == case_id)
            .order_by(OutcomeRecord.revision_number.desc(), OutcomeRecord.id.desc())
            .limit(1)
        )
        return CaseClosureEvidence(int(alerts or 0), int(tasks or 0), outcome_id)
