"""Create deterministic synthetic R1 lifecycle data through application handlers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid5

from vinami.clinical_case.application.lifecycle import (
    OpenClinicalCase,
    OpenClinicalCaseHandler,
)
from vinami.clinical_case.application.lifecycle import (
    UnitOfWorkFactory as ClinicalCaseUnitOfWorkFactory,
)
from vinami.clinical_case.domain.model import ClinicalPriority
from vinami.identity.adapters.development import DevelopmentIdentityAdapter
from vinami.identity.domain.model import ClinicalRole, ClinicalUser
from vinami.patient.application.lifecycle import (
    RegisterPatient,
    RegisterPatientHandler,
    SafeDemographicSummary,
    StartEncounter,
    StartEncounterHandler,
)
from vinami.patient.application.lifecycle import (
    UnitOfWorkFactory as PatientUnitOfWorkFactory,
)
from vinami.shared.actor import ActorContext
from vinami.shared.config import Settings
from vinami.shared.container import AppContainer
from vinami.shared.logging import log_event

SEED_NAMESPACE = UUID("62e2f5a0-98d8-4c59-bde8-35521ea06110")
ACTOR_ID = uuid5(SEED_NAMESPACE, "r1-development-actor")
BASE_TIME = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)

CASES = (
    (
        "high-priority-review",
        "45-64",
        "female",
        "Emergency Department",
        ClinicalPriority.CRITICAL,
    ),
    ("observation", "65-74", "male", "Observation Unit", ClinicalPriority.ROUTINE),
    ("repeat-assessment", "35-44", None, "Emergency Department", ClinicalPriority.URGENT),
)


def main() -> None:
    """Seed three lifecycle-only cases idempotently and project their audit/timeline."""
    container = AppContainer.create(Settings())
    try:
        container.database.probe_readiness()
        DevelopmentIdentityAdapter(container.database.session_factory).ensure_actor(
            ClinicalUser(
                id=ACTOR_ID,
                display_name="R1 Development Seed Actor",
                role=ClinicalRole.COORDINATOR,
            )
        )
        patient_factory = cast(PatientUnitOfWorkFactory, container.unit_of_work)
        case_factory = cast(ClinicalCaseUnitOfWorkFactory, container.unit_of_work)
        patient_handler = RegisterPatientHandler(patient_factory)
        encounter_handler = StartEncounterHandler(patient_factory)
        case_handler = OpenClinicalCaseHandler(case_factory)
        case_ids: list[str] = []
        for index, (name, age_band, sex, location, priority) in enumerate(CASES):
            occurred_at = BASE_TIME + timedelta(minutes=index * 10)
            actor = ActorContext(
                actor_id=ACTOR_ID,
                actor_role=ClinicalRole.COORDINATOR.value,
                correlation_id=uuid5(SEED_NAMESPACE, f"correlation:{name}"),
                request_source="deterministic-r1-seed",
            )
            patient = patient_handler.execute(
                RegisterPatient(
                    command_id=uuid5(SEED_NAMESPACE, f"command:patient:{name}"),
                    actor=actor,
                    idempotency_key=f"r1-seed-patient-{name}",
                    patient_reference=f"R1-SYN-{index + 1:03d}",
                    safe_demographic_summary=SafeDemographicSummary(age_band, sex),
                    requested_at=occurred_at,
                    patient_id=uuid5(SEED_NAMESPACE, f"patient:{name}"),
                )
            )
            encounter = encounter_handler.execute(
                StartEncounter(
                    command_id=uuid5(SEED_NAMESPACE, f"command:encounter:{name}"),
                    actor=actor,
                    idempotency_key=f"r1-seed-encounter-{name}",
                    patient_id=patient.patient_id,
                    location=location,
                    arrival_at=occurred_at + timedelta(minutes=1),
                    external_reference=f"R1-ENC-{index + 1:03d}",
                    encounter_id=uuid5(SEED_NAMESPACE, f"encounter:{name}"),
                )
            )
            clinical_case = case_handler.execute(
                OpenClinicalCase(
                    command_id=uuid5(SEED_NAMESPACE, f"command:case:{name}"),
                    actor=actor,
                    idempotency_key=f"r1-seed-case-{name}",
                    encounter_id=encounter.encounter_id,
                    opening_reason=f"R1 synthetic {name} lifecycle demonstration",
                    priority=priority,
                    requested_at=occurred_at + timedelta(minutes=2),
                    case_id=uuid5(SEED_NAMESPACE, f"case:{name}"),
                )
            )
            case_ids.append(str(clinical_case.case_id))
        dispatch = container.event_dispatcher().dispatch_pending(limit=100)
        log_event(
            container.logger,
            "r1_seed_completed",
            clinical_cases=case_ids,
            events_published=dispatch.published,
            dead_lettered=dispatch.dead_lettered,
        )
        if dispatch.dead_lettered:
            raise RuntimeError("R1 seed produced a dead-letter event")
    finally:
        container.database.dispose()


if __name__ == "__main__":
    main()
