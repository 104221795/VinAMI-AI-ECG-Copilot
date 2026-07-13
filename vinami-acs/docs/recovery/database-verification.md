# Database Verification

## Clean Startup

The required clean startup was executed:

```powershell
docker compose down -v --remove-orphans
docker compose up --build -d
```

The first build invocation exceeded the command timeout while Docker continued work; a second
invocation encountered a temporary container-name conflict from the overlapping build. After the
build completed, `docker compose up -d` started the stack. This host-level timing issue is separate
from the application defects below.

Before manual migration:

```text
public_table_count = 0
alembic current = no revision
API /health = 200
API /ready = 200
worker = exited, UndefinedTable(workflow_due_timers)
```

This is a blocking deployment defect. Database connectivity is not schema readiness.

## Manual Migration

```powershell
docker compose exec -T api alembic upgrade head
```

Applied revisions:

```text
e8925090e0cb initial_system_of_record
c4d7e8f9a1b2 internal_event_delivery
f5a9c2d6e4b1 workflow_engine
```

Verified state:

```text
Alembic current: f5a9c2d6e4b1 (head)
public tables: 28
constraints: 84
indexes: 108
enum types: 11
```

Tables:

```text
alembic_version, alerts, audit_logs, clinical_cases, clinical_pathways,
clinical_tasks, clinical_teams, clinical_users, clinical_workflows,
ecg_ai_results, ecg_findings, ecg_studies, encounters, event_consumptions,
lab_orders, lab_results, model_registry, outbox_events, outcomes, patients,
risk_scores, symptom_observations, timeline_events, troponin_timelines,
vital_observations, workflow_command_receipts, workflow_due_timers,
workflow_transition_history
```

## Migration Drift

`alembic check` failed. Alembic detected that ORM metadata would remove two constraints that the
migration created:

```text
uq_alert_workflow_effect
uq_clinical_task_workflow_effect
```

The migration and current declarative mappings are not in sync.

## Persistence and Restart

A deterministic graph was persisted through domain aggregates and `SQLAlchemyUnitOfWork`:

```text
patient:   11111111-1111-1111-1111-111111111111
encounter: 22222222-2222-2222-2222-222222222222
case:      33333333-3333-3333-3333-333333333333
```

The transaction created one row in each aggregate table and three outbox rows. Data remained after
restarting PostgreSQL, API, and worker. The Docker volume therefore provides restart persistence.

The API still returned an empty patient and case list, proving the placeholder API does not read
the persisted records.

## Production Mapping Failure

After migration, workflow creation through the normal `AppContainer` failed and rolled back:

```text
NoReferencedTableError:
Foreign key associated with column 'clinical_workflows.decision_actor_id'
could not find table 'clinical_users'
```

The same incomplete runtime metadata caused audit projection failure. `orm_registry.metadata()`
imports every mapping for Alembic, but normal API/worker composition does not call it. Integration
tests run Alembic in-process first, so they accidentally preload mappings and hide this defect.

## Clinical Persistence Fidelity Gaps

- `symptom_observations` does not persist triage `DataStatus`.
- `lab_results` omits assay manufacturer, analyzer, reference limit, normalized ratio, quality
  flags, and renal-function context.
- Troponin repository synchronization replaces domain order/collection timestamps with adapter
  current time and rehydrates assays with default metadata.
- `ecg_ai_results` omits provider name, start/completion pair, input quality, warnings, provenance,
  and failure reason from the normalized provider contract.
- Rule specifications/versions have no registry table; only pathway output text/facts are stored.
- Audit append-only behavior is conventional, not enforced by database privileges or triggers.

## Assessment

Relational schema foundation: **partial but substantial**.

Deployment readiness: **failing**.

Data fidelity for triage, troponin, AI provenance, and rules: **insufficient for the documented
contracts**.
