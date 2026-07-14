"""Load context-owned SQLAlchemy mappings into one metadata registry for Alembic."""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import configure_mappers

from vinami.shared.persistence import Base


def metadata() -> MetaData:
    """Import every infrastructure mapping exactly when schema metadata is required."""
    from vinami.alerts.adapters import persistence as alerts_persistence
    from vinami.audit.adapters import persistence as audit_persistence
    from vinami.clinical_case.adapters import persistence as case_persistence
    from vinami.ecg.adapters import persistence as ecg_persistence
    from vinami.ecg.adapters import r3_persistence as ecg_r3_persistence
    from vinami.identity.adapters import persistence as identity_persistence
    from vinami.model_registry.adapters import persistence as model_persistence
    from vinami.patient.adapters import persistence as patient_persistence
    from vinami.reasoning.adapters import persistence as reasoning_persistence
    from vinami.shared import idempotency_persistence
    from vinami.timeline.adapters import persistence as timeline_persistence
    from vinami.triage.adapters import persistence as triage_persistence
    from vinami.troponin.adapters import persistence as troponin_persistence
    from vinami.workflow.adapters import decision_persistence
    from vinami.workflow.adapters import persistence as workflow_persistence

    _ = (
        alerts_persistence,
        audit_persistence,
        case_persistence,
        ecg_persistence,
        ecg_r3_persistence,
        identity_persistence,
        model_persistence,
        patient_persistence,
        reasoning_persistence,
        idempotency_persistence,
        timeline_persistence,
        triage_persistence,
        troponin_persistence,
        workflow_persistence,
        decision_persistence,
    )
    return Base.metadata


def initialize_mappings() -> MetaData:
    """Load and configure the exact ORM registry used by API, worker, tests, and Alembic."""
    registry_metadata = metadata()
    configure_mappers()
    return registry_metadata
