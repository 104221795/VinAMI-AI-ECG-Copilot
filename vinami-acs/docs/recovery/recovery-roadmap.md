# Recovery Roadmap

## Gate 0: Clinical Safety and Runtime Integrity

Do not expose workflow commands until all items pass.

1. Make safety facts system-owned. Remove physician decision, conflict, alert count, ECG quality,
   and troponin-derived state from arbitrary caller `facts_patch`.
2. Implement a typed, actor-provenanced `RecordPhysicianDecision` command and require it in
   cath-lab review, transfer, discharge review, and closure guards.
3. Establish one closure authority. Coordinate `ClinicalCase` closure through workflow and
   unresolved critical-alert checks in one application transaction.
4. Load the complete SQLAlchemy mapping registry in API, worker, scripts, and tests through one
   explicit infrastructure initialization path.
5. Add a production-composition integration test that does not rely on Alembic imports in the same
   process.
6. Fix default audit/timeline projection and require every accepted mutation to have an audit
   consumer or an explicit synchronous audit write.
7. Correct the canonical demonstration notice and remove mojibake.

Exit evidence:

- actorless spoof proof is rejected;
- typed physician decision is persisted and audited;
- runtime workflow start/transition succeeds in a fresh process;
- case event publishes with audit/timeline rows;
- patient and encounter actions are audited.

## Gate 1: Honest Deployment

1. Add a one-shot migration service or equivalent deployment step.
2. Gate API readiness and worker startup on Alembic head.
3. Fix the two ORM/migration constraint drift findings.
4. Add worker database retry/backoff, healthcheck, and a justified restart policy.
5. Make seed deterministic and domain/application-driven, or rename it as a database probe.
6. Add outbox pending/retry/dead-letter metrics and operational alerts.

Exit evidence:

```powershell
docker compose down -v
docker compose up --build -d
docker compose ps
docker compose exec -T api alembic current
```

All services must remain healthy, schema must be at head without manual intervention, and a
PostgreSQL restart must not permanently terminate the worker.

## Gate 2: First Real Vertical Slice

Implement only:

1. Register patient.
2. Start encounter.
3. Open suspected ACS case and initial workflow.
4. List active cases from PostgreSQL.
5. Retrieve one case detail.
6. Retrieve case timeline/audit.

Required cross-cutting contracts:

- Pydantic v2 DTOs;
- actor context placeholder;
- correlation propagation;
- idempotency key;
- expected aggregate version where applicable;
- RFC 7807 errors;
- explicit UoW transaction;
- no ORM in routers;
- contract and PostgreSQL tests.

This slice is complete only when the API returns persisted data and the outbox produces audit and
timeline records.

## Gate 3: Evidence Capture

1. Triage symptoms/vitals with explicit known/missing/unknown persistence.
2. ECG study creation, immutable evidence reference, quality assessment, provider request/result
   lifecycle, and failure path.
3. Troponin order/collection/result timeline with lossless assay/provenance persistence.
4. Dynamic ECG as a serial study timeline, not only a repeat task.
5. Case read model combining facts without placing rules in queries or UI.

## Gate 4: Reasoning and Human Workflow

1. Persist approved versioned demonstration rule artifacts.
2. Evaluate evidence and store full decision traces.
3. Detect conflict and raise a review alert.
4. Execute workflow commands from system-owned facts.
5. Create/complete tasks and acknowledge/resolve alerts.
6. Record physician decisions and consequential review requests.
7. Expose complete audit/timeline/model provenance queries.

## Gate 5: ECG Adapter and UI Reconnection

1. Keep mock provider deterministic and fully normalize/persist its contract.
2. Add Torch adapter only after provider contract tests and artifact compatibility checks.
3. Reconnect Streamlit only to stable `/api/v1` contracts.
4. Remove synthetic production-mode data and keep research/demo labels visible.
5. Run browser, accessibility, visual, safety, performance, and security gates.

## Priority Defects

| Priority | Defect | Blocks |
|---|---|---|
| P0 | Physician confirmation can be forged | All consequential workflow work |
| P0 | ClinicalCase closure bypasses workflow safety | Case closure |
| P0 | Runtime ORM registry incomplete | Workflow, event projection |
| P0 | Default audit projection dead-letters | Auditability |
| P0 | Patient/encounter events publish without audit handlers | Acceptance AC-02 |
| P1 | Migrations absent from startup; readiness false-positive | Clean deployment |
| P1 | Worker exits on PostgreSQL restart | Timers and events |
| P1 | Clinical API is placeholder-only | All 20 capabilities |
| P1 | Persistence loses triage/troponin/AI provenance | Clinical data integrity |
| P2 | Full lint/type gate and ignored dashboard model | Repository reproducibility |

## Recommendation

**NO-GO for feature/UI vertical-slice development.**

**GO only for Gates 0-2 as a backend recovery program.** Do not begin ECG/Troponin UI or broader
workflow pages until the first real Patient -> Encounter -> Case -> Audit slice passes from a clean
Compose startup.
