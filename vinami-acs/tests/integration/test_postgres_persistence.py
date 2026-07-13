"""PostgreSQL repository, unit-of-work, rollback, and concurrency tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from vinami.audit.adapters.persistence import OutboxEventRecord
from vinami.clinical_case.adapters.persistence import ClinicalCaseRecord
from vinami.clinical_case.domain.model import ClinicalCase, ClinicalPriority
from vinami.patient.adapters.persistence import EncounterRecord, PatientRecord
from vinami.patient.domain.model import (
    Demographics,
    Encounter,
    Patient,
    PatientIdentifier,
    PersonName,
)
from vinami.shared.domain import OptimisticConcurrencyError
from vinami.shared.unit_of_work import SQLAlchemyUnitOfWork

NOW = datetime(2026, 7, 13, 0, 0, tzinfo=UTC)


def _patient() -> Patient:
    return Patient.register(
        PatientIdentifier("integration", f"P-{uuid4()}"),
        PersonName("Mai", "Tran"),
        Demographics(None, None),
        NOW,
    )


def _case_graph() -> tuple[Patient, Encounter, ClinicalCase]:
    patient = _patient()
    encounter = Encounter.start(patient.id, "Emergency", NOW)
    case = ClinicalCase.open(encounter.id, "suspected ACS workflow", ClinicalPriority.URGENT, NOW)
    return patient, encounter, case


def test_patient_case_graph_and_outbox_are_committed_atomically(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Patient, encounter, case, and their events persist in one database transaction."""
    patient, encounter, case = _case_graph()

    with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
        uow.patients.add(patient)
        uow.encounters.add(encounter)
        uow.cases.add(case)
        uow.collect_events([patient, encounter, case])
        uow.commit()

    with postgres_session_factory() as session:
        assert session.get(PatientRecord, patient.id) is not None
        assert session.get(EncounterRecord, encounter.id).patient_id == patient.id
        assert session.get(ClinicalCaseRecord, case.id).encounter_id == encounter.id
        assert session.scalar(select(func.count()).select_from(OutboxEventRecord)) == 3


def test_unit_of_work_rolls_back_uncommitted_patient(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Exiting an uncommitted unit of work leaves no partial patient row."""
    patient = _patient()
    with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
        uow.patients.add(patient)

    with postgres_session_factory() as session:
        assert session.get(PatientRecord, patient.id) is None


def test_case_repository_detects_optimistic_concurrency(
    postgres_session_factory: sessionmaker[Session],
) -> None:
    """Two stale case updates cannot both be committed."""
    patient, encounter, case = _case_graph()
    with SQLAlchemyUnitOfWork(postgres_session_factory) as uow:
        uow.patients.add(patient)
        uow.encounters.add(encounter)
        uow.cases.add(case)
        uow.commit()

    first = SQLAlchemyUnitOfWork(postgres_session_factory)
    stale = SQLAlchemyUnitOfWork(postgres_session_factory)
    try:
        first.__enter__()
        stale.__enter__()
        first_case = first.cases.get(case.id)
        stale_case = stale.cases.get(case.id)
        assert first_case is not None
        assert stale_case is not None
        first_case.begin_review(expected_version=1)
        stale_case.begin_review(expected_version=1)
        first.cases.save(first_case)
        stale.cases.save(stale_case)
        first.commit()
        with pytest.raises(OptimisticConcurrencyError):
            stale.commit()
    finally:
        first.__exit__(None, None, None)
        stale.__exit__(None, None, None)
