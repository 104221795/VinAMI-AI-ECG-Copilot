# Sprint 3 Persistence Model

## Boundary

Sprint 3 establishes the PostgreSQL system of record for VinAMI ACS. It implements domain aggregates and infrastructure adapters only. It exposes no new API endpoint, Streamlit workflow, clinical threshold, model inference, or autonomous action.

## Ownership and Mapping

| Context | Aggregate or facts | Relational tables |
|---|---|---|
| Patient | `Patient`, `Encounter` | `patients`, `encounters` |
| ACS Clinical Case | `ClinicalCase` | `clinical_cases` |
| Triage | symptom and vital facts | `symptom_observations`, `vital_observations` |
| ECG | `ECGStudy`, normalized result and findings | `ecg_studies`, `ecg_ai_results`, `ecg_findings` |
| Troponin | `TroponinTimeline`, orders and results | `troponin_timelines`, `lab_orders`, `lab_results` |
| Reasoning | declared score and pathway records | `risk_scores`, `clinical_pathways` |
| Workflow | `ClinicalWorkflow`, `ClinicalTask` | `clinical_workflows`, `clinical_tasks` |
| Alerts | `Alert` | `alerts` |
| Timeline and Audit | immutable projections and outcomes | `timeline_events`, `audit_logs`, `outcomes`, `outbox_events` |
| Model Registry | `ModelRegistryEntry` | `model_registry` |
| Identity | actor/team placeholder | `clinical_users`, `clinical_teams` |

## Data Rules

- Primary and foreign identifiers are UUIDs. Domain timestamps are timezone-aware and normalized to UTC by a persistence type.
- Every aggregate is framework-free. SQLAlchemy mappings live in each context's `adapters/persistence.py`; repositories map records to domain objects.
- `clinical_cases.version` and `clinical_workflows.version` use SQLAlchemy version predicates. A stale flush becomes an explicit `OptimisticConcurrencyError`.
- Enums are PostgreSQL named enum types. The initial migration drops them explicitly during downgrade so an upgrade/downgrade cycle is repeatable.
- JSONB is limited to acquisition metadata, pathway facts, audit payloads, timeline payloads, and versioned outbox payloads. Findings, measurements, symptoms, vitals, assignments, and statuses remain relational.
- The Unit of Work stages versioned `EventEnvelope` records as `outbox_events` in the same commit as aggregate rows. The internal dispatcher tracks `pending`, `processing`, `published`, and `dead_letter` state, retry metadata, lease timestamps, and idempotent handler consumption in `event_consumptions`.

## Integrity and Deletion

Clinical ownership uses foreign keys. Case-owned evidence and observations use `CASCADE`; identity references use `SET NULL` or `RESTRICT` according to whether historical provenance must be preserved. Patient and encounter identifiers have uniqueness constraints, as do model name/version, ECG input reference, one ECG AI result per study, one troponin timeline per case, one workflow per case, and outbox event ID.

## Verification

The integration suite creates a disposable PostgreSQL database, runs Alembic, validates patient-to-encounter-to-case persistence and outbox atomicity, verifies rollback and stale writes, then downgrades to base and upgrades again.
