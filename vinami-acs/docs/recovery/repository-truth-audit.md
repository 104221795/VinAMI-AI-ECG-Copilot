# VinAMI ACS Repository Truth Audit

Audit date: 2026-07-13

Scope: repository source, architecture documents, ADRs, migrations, PostgreSQL state,
FastAPI/OpenAPI behavior, event delivery, workflow execution, tests, Docker Compose runtime,
and the preserved VinStroke ECG research artifacts.

The independent ConvNeXtV2/PTB-XL prototype was inventoried and preserved. Its checkpoint,
reports, notebook, and five-label metrics are evidence for an ECG research prototype only.
They are not evidence that the VinAMI ACS workflow backend works.

## Executive Verdict

Estimated backend completion is **20%**. This percentage represents reusable architecture and
internal implementation, not user-facing completion. **Zero of the 20 required backend
acceptance capabilities works end to end through the versioned API.**

The repository contains meaningful domain models, relational mappings, three reversible
Alembic migrations, an explicit Unit of Work, a transactional outbox, a declarative workflow
engine, a deterministic mock ECG provider, and focused internal tests. It does not contain a
working ACS application API. Several internal paths that pass tests fail in a clean runtime.

## Blocking Findings

1. Clean Compose startup creates a PostgreSQL database with zero application tables. No service
   runs `alembic upgrade head`.
2. `/ready` returns `200` against that empty database because it checks only `SELECT 1`.
3. The worker crashes on clean startup because `workflow_due_timers` does not exist.
4. After manual migration, the normal composition root does not load all SQLAlchemy mappings.
   Starting a workflow fails with `NoReferencedTableError` for `clinical_users`.
5. The same mapping defect causes `ClinicalCaseOpened.v1` projection delivery to retry three
   times and enter dead-letter. No case audit or timeline record is created.
6. `PatientRegistered.v1` and `EncounterStarted.v1` are marked published with zero handlers, so
   those accepted actions produce no audit projection.
7. The workflow accepts caller-controlled `facts_patch`. A caller can set
   `physician_decision_recorded=true` with no actor and no typed `PhysicianDecision`, then reach
   `CATH_LAB_REVIEW`. This violates the human-in-the-loop safety boundary.
8. `ClinicalCase.close()` is independent from workflow, troponin, physician decision, and alert
   state. Its domain guard only requires `UNDER_REVIEW` and a version match.
9. Every `/api/v1/*` clinical route is a generic hard-coded empty collection. There are no
   clinical command, detail, action, upload, or case-workspace endpoints.
10. `alembic check` fails because migration metadata and ORM metadata disagree about task/alert
    workflow-effect unique constraints.
11. Restarting PostgreSQL alone terminates the worker. There is no retry loop or restart policy.
12. The complete static gate fails: Ruff has one dashboard import-order failure and mypy has nine
    dashboard import-resolution failures. Backend-only Ruff and mypy pass.

## Layer Truth

| Layer | Assessment | Runtime meaning |
|---|---|---|
| Domain | Partial, useful | Aggregates and invariants exist, but safety and cross-aggregate coordination are incomplete. |
| Application | Mostly missing | Workflow has handlers; triage/troponin have pure apply functions; other contexts have package markers only. |
| Persistence | Partial | Schema and repositories exist, but runtime registry loading and persistence fidelity have defects. |
| Events | Partial and failing | Outbox mechanics are implemented; default audit/timeline projection fails in runtime. |
| Workflow | Partial and safety-blocked | Declarative engine exists; production composition fails and physician confirmation can be forged. |
| API | Placeholder | Platform endpoints work; all clinical routes return empty envelopes. |
| Worker | Failing | Requires manual migration, fails default projection, and exits on PostgreSQL interruption. |
| Tests | Partial | 45 tests pass with 79% statement coverage, but critical production wiring is untested and fixture-masked. |

## Architecture Violations

- `workflow/adapters/persistence.py` imports `alerts/adapters/persistence.py` directly. This crosses
  a bounded-context infrastructure boundary instead of using a published contract or event.
- The production composition root does not initialize the complete ORM registry. Alembic does,
  which makes integration tests pass while runtime application/worker sessions fail.
- Workflow authorization facts are caller-owned. Safety-critical facts must be derived from
  persisted, actor-provenanced commands, not accepted as arbitrary patches.
- The HTTP correlation ID is returned in response headers but is not bound into structured request
  logs or domain `EventContext`.
- One three-aggregate audit transaction emitted three distinct correlation IDs and three null
  actor IDs. Command-level causality is therefore not established in product code.
- No application layer coordinates `ClinicalCase` closure with workflow, alerts, troponin, or
  physician decision.
- Shared event handlers import concrete ORM records. This is infrastructure code placed in
  `shared`, and its runtime import set is incomplete.
- The root `.gitignore` rule `models/` ignores
  `vinami-acs/apps/dashboard/models/view_models.py`, making a clean clone non-reproducible.

## Clean Runtime Evidence

```text
clean public table count: 0
/health: 200 healthy
/ready: 200 ready
worker: Exited (1), relation "workflow_due_timers" does not exist
seed: clinical_records_created=0
```

After manual migration:

```text
Alembic head: f5a9c2d6e4b1
public tables: 28
constraints: 84
indexes: 108
PostgreSQL enums: 11
```

Runtime domain/UoW audit case:

```text
patients=1, encounters=1, clinical_cases=1, outbox_events=3
PatientRegistered.v1: published, handlers=0
EncounterStarted.v1: published, handlers=0
ClinicalCaseOpened.v1: dead_letter, attempts=3
audit_logs=0, timeline_events=0
```

Workflow safety proof:

```text
state=CATH_LAB_REVIEW
typed_physician_decision=None
actorless_transitions=8
```

## Exact Commands Executed

Repository and source inspection used `rg --files`, `rg --files --hidden -g !.git`, targeted
`Get-Content -Raw` reads for all architecture/ADR/MVP/source/migration/test files, artifact
inventory commands, static import scans, and `git status --short`.

Runtime and quality commands:

```powershell
docker compose down -v --remove-orphans
docker compose up --build -d
docker compose up -d
docker compose ps -a
docker compose logs --no-color --tail=200 worker api dashboard
docker compose exec -T postgres psql -U vinami -d vinami_acs -c "SELECT count(*) AS public_table_count FROM pg_tables WHERE schemaname='public';"
docker compose exec -T api alembic current
curl.exe -s -i http://127.0.0.1:8000/health
curl.exe -s -i http://127.0.0.1:8000/ready
curl.exe -s -i http://127.0.0.1:8501/_stcore/health
docker compose exec -T api python -m scripts.seed
docker compose exec -T api ruff format --check apps src tests scripts
docker compose exec -T api ruff check apps src tests scripts
docker compose exec -T api mypy apps src scripts
docker compose exec -T api mypy src apps/api apps/worker scripts
docker compose exec -T api pytest -q
docker compose exec -T api pytest -q --cov=vinami --cov=apps.api --cov=apps.worker --cov-report=term-missing
docker compose exec -T api pytest --collect-only -q
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic current
docker compose exec -T api alembic check
docker compose exec -T postgres psql -U vinami -d vinami_acs -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
docker compose restart worker
docker compose restart postgres api worker
docker compose restart postgres
docker compose exec -T api python -m scripts.replay_events --event-type ClinicalCaseOpened.v1 --start 2026-07-13T00:00:00+00:00 --end 2026-07-13T23:59:59+00:00
curl.exe -s -i http://127.0.0.1:8000/api/v1/clinical-cases
curl.exe -s -i -X POST http://127.0.0.1:8000/api/v1/patients -H "Content-Type: application/json" -d "{}"
curl.exe -s -i http://127.0.0.1:8000/api/v1/clinical-cases/00000000-0000-0000-0000-000000000000
curl.exe -s -i "http://127.0.0.1:8000/api/v1/patients?page=0"
curl.exe -s -i -H "X-Correlation-ID: audit-correlation-20260713" http://127.0.0.1:8000/api/v1/clinical-cases
git check-ignore -v vinami-acs/apps/dashboard/models/view_models.py
```

Additional `docker compose exec -T api python -c ...` probes created one deterministic
patient/encounter/case through domain repositories and UoW, attempted workflow startup, enumerated
OpenAPI, and proved the physician-confirmation bypass. The exact IDs and results are recorded in
the database, event, and workflow verification documents.

## Recommendation

**NO-GO for a clinical/product vertical slice or Sprint 12 feature work.**

Proceed only with a constrained backend recovery slice that closes the safety bypass, fixes ORM
runtime registration and event projection, makes migrations/readiness/worker startup honest, and
then exposes Patient -> Encounter -> Clinical Case through real application/API contracts.
