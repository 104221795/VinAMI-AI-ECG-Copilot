# R1 Test Report

Date: 2026-07-13. Environment: Python 3.12 clean Docker Compose with PostgreSQL 16.

## Results

| Gate | Result |
|---|---|
| Targeted R1 domain/architecture/API | 18 passed |
| Focused migration/persistence/R0/R1 integration | 19 passed |
| Full backend suite | 67 passed, 0 failed, 0 skipped |
| Coverage | 87% over 3,865 statements |
| Ruff format | 342 files formatted |
| Ruff lint | Pass |
| mypy | Pass, 162 source files |
| Alembic current | `d4c8a91e7b32 (head)` |
| Alembic check | No new upgrade operations |

Coverage for the R1 delivery and lifecycle application modules is 96-100%. Aggregate coverage also
contains deliberately incomplete future modules and must not be interpreted as product completion.

## PostgreSQL and runtime evidence

- Migration upgrade/downgrade/upgrade and autogenerate drift check passed.
- Same idempotency key and payload returned the original result after application restart.
- Concurrent duplicate requests returned one Patient UUID.
- Same key with another payload returned 409.
- One-active-case policy and foreign keys were exercised against PostgreSQL.
- Seed executed twice: first run published nine events; second run published zero new events.
- Seed state: 3 Patients, 3 Encounters, 3 Cases, 9 idempotency rows, 9 audit rows, and 9 timeline rows.
- A separate live API lifecycle was processed by the running worker: three published events, three
  timeline rows, three audit rows, one shared correlation ID, and zero dead letters.
- API and worker restart preserved case state and projections.

## Warnings

Three non-blocking dependency/instrumentation warnings remain: the upstream Starlette TestClient
deprecation, a Pydantic/FastAPI alias warning observed during the concurrent-client test, and the
coverage notice that `apps.worker` was not imported by coverage instrumentation. Worker execution
was verified separately from structured runtime logs.

## Commands

```powershell
docker compose run --rm --no-deps api python -m pytest tests/unit/test_r1_lifecycle_domain.py tests/architecture/test_dependency_rules.py tests/integration/test_r1_lifecycle_api.py -q
docker compose run --rm --no-deps api python -m pytest tests/integration/test_migrations.py tests/integration/test_postgres_persistence.py tests/integration/test_r0_recovery.py tests/integration/test_r1_lifecycle_api.py -q
docker compose down -v --remove-orphans
docker compose up --build -d
docker compose exec -T api alembic current
docker compose exec -T api alembic check
docker compose run --rm api python scripts/seed.py
docker compose restart api worker
docker compose run --rm --no-deps api python -m ruff format --check .
docker compose run --rm --no-deps api python -m ruff check .
docker compose run --rm --no-deps api python -m mypy
docker compose run --rm --no-deps api python -m pytest --cov=src/vinami --cov=apps.api --cov=apps.worker --cov-report=term-missing -q
```

Additional `Invoke-RestMethod` and PostgreSQL queries verified real API reads, projection contents,
restart persistence, idempotency counts, outbox status, and dead-letter count.
