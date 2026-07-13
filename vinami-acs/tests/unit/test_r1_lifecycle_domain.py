"""Focused domain tests for the R1 lifecycle foundation."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from vinami.clinical_case.domain.model import ClinicalCase, ClinicalPriority
from vinami.patient.domain.model import Demographics, Encounter, Patient, PatientIdentifier
from vinami.shared.domain import DomainInvariantError

NOW = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)


def test_patient_reference_is_non_empty_and_versioned() -> None:
    with pytest.raises(DomainInvariantError, match="identifier value"):
        PatientIdentifier("vinami.r1.synthetic", " ")

    patient = Patient.register(
        PatientIdentifier("vinami.r1.synthetic", "SYN-001"),
        None,
        Demographics(None, "female", "45-64"),
        NOW,
    )
    assert patient.version == 1
    assert patient.registered_at == patient.updated_at == NOW


def test_encounter_rejects_nil_patient_and_naive_arrival() -> None:
    with pytest.raises(DomainInvariantError, match="timezone-aware"):
        Encounter.start(uuid4(), "Emergency", datetime(2026, 7, 13, 8, 0))

    with pytest.raises(DomainInvariantError, match="nil UUID"):
        Encounter.start(UUID(int=0), "Emergency", NOW)


def test_case_uses_explicit_priority_and_utc_version() -> None:
    clinical_case = ClinicalCase.open(uuid4(), "Suspected ACS review", ClinicalPriority.URGENT, NOW)
    assert clinical_case.priority is ClinicalPriority.URGENT
    assert clinical_case.version == 1
    assert clinical_case.updated_at == NOW
