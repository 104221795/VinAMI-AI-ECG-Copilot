# Test Quality Report

## Results

```text
Ruff format: 166 files already formatted
Full Ruff lint: failed, 1 dashboard import-order issue
Backend-only Ruff lint: passed
Full mypy: failed, 9 dashboard import-resolution errors
Backend-only mypy: passed, 138 source files
Pytest: 45 passed, 1 warning
Statement coverage: 79% over the selected vinami/API modules
```

The warning is an upstream FastAPI/Starlette TestClient deprecation concerning `httpx`.

## Test Counts

| Category | Count |
|---|---:|
| Architecture | 6 |
| Contract | 1 |
| Integration | 14 |
| Unit | 24 |
| Total | 45 |

## What the Tests Prove

- Selected domain invariants execute without frameworks.
- Patient/encounter/case persistence and outbox atomicity work in the test fixture.
- ClinicalCase optimistic concurrency is translated from SQLAlchemy stale updates.
- Alembic can downgrade to base and upgrade to head in a disposable database.
- Synthetic event handlers demonstrate retry, dead-letter, idempotency, and replay mechanics.
- The declarative workflow has focused unit paths and two PostgreSQL persistence tests.
- Troponin domain delta checks and mock ECG score determinism have unit coverage.

## What the Tests Do Not Prove

- Any of the 20 clinical capabilities through FastAPI.
- Default audit/timeline projection success.
- Production composition-root ORM registration.
- Worker clean startup or database reconnect.
- Real physician confirmation and actor authorization.
- ClinicalCase/workflow closure consistency.
- API idempotency, expected version, rollback, RFC 7807, pagination, filtering, permissions, or
  provider failures.
- Triage persistence, ECG repository round trip, troponin metadata round trip, pathway persistence,
  alert lifecycle persistence, model registry activation, timeline queries, or audit queries.
- Malformed upload, timeout, Torch checkpoint, or explanation behavior.
- Dynamic ECG behavior.

## Fixture Masking Defect

The session-scoped PostgreSQL fixture calls Alembic in the pytest process. Alembic calls
`orm_registry.metadata()`, importing all mappings before repository tests run. Production
`AppContainer` does not do this. Therefore:

- workflow persistence tests pass;
- the same workflow start fails in the production container with `NoReferencedTableError`.

This is a test-environment fidelity defect, not evidence that SQLAlchemy is unreliable.

## Coverage Caveats

The 79% aggregate is not product coverage:

- empty package markers count as 100%;
- imported mapping declarations count as covered without behavior assertions;
- triage domain/application are 0%;
- troponin application is 0%;
- audit/timeline domain behavior is 0%;
- ECG persistence is 56%;
- troponin persistence is 53%;
- the worker module was not imported by coverage;
- API coverage is high because the API has almost no clinical behavior.

## Architecture Test Gaps

Existing tests correctly prohibit several domain/framework imports and workflow/model imports. They
do not currently enforce all documented rules:

- application layer importing concrete adapters/SQLAlchemy/FastAPI;
- dashboard importing repositories, domain aggregates, workflow rules, or provider code;
- routers importing ORM/concrete providers/rules;
- cross-context adapter imports;
- full context API/application files having concrete behavior;
- complete ORM registry initialization in each deployable process.

## Static Quality

No frontend code was modified in this audit. The full gate remains failed because dashboard imports
are script-relative and Ruff-unordered. The root `.gitignore` also excludes the dashboard
`models/` directory. Backend-only lint and strict typing pass.

## Assessment

The suite is a useful component test suite. It is not a product, contract, clinical safety, or
runtime acceptance suite. Passing 45 tests does not justify a Sprint 9-11 completion claim.
