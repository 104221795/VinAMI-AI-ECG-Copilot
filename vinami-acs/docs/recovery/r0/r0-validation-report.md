# R0 Validation Report

Date: 2026-07-13. Scope: P0 clinical-safety boundaries, runtime integrity, persistence integrity, and production wiring. This is not clinical or production validation.

## Decision

R0 acceptance criteria pass. Recommendation: **GO for R1's first narrow backend vertical slice only**. The recommendation does not authorize clinical use, UI expansion, or production deployment.

## Quality gate

| Check | Result |
|---|---|
| Ruff format | 322 files formatted |
| Ruff lint | Pass |
| mypy | Pass, 152 source files |
| pytest | 55 passed, 1 non-blocking upstream warning |
| Coverage | 85% over 3,097 statements |
| Alembic current | `a7d3f0b2c6e1 (head)` |
| Alembic drift | None |
| Clean migration service | Exit 0 |
| Readiness | HTTP 200 only at required schema/head |
| Runtime outbox | 3 published, 0 dead-letter |
| Restart persistence | Pass for patient, encounter, case, event, audit, timeline |

## Acceptance evidence

All generic decision patch, cath-lab authority, case closure, actor context, provenance, ORM bootstrap, migration/readiness, event repair, immutable audit, static-quality, and regression-test criteria passed. A direct runtime probe confirms the worker executes registered handlers and persists projections.

## Exact commands executed

```powershell
git rev-parse HEAD
git branch --show-current
git status --short
docker compose ps -a
docker compose images
docker compose exec -T api alembic current
docker compose exec -T api alembic check
docker compose down -v --remove-orphans
docker compose up --build -d
docker compose up -d
docker compose ps
docker compose logs migrate
docker compose logs --tail=80 worker
docker compose exec -T postgres psql -U vinami -d vinami_acs -c "<schema/outbox/audit/timeline verification queries>"
docker compose restart api worker
docker compose restart postgres
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/ready
docker compose build api
docker compose run --rm --no-deps api python -m ruff format --check .
docker compose run --rm --no-deps api python -m ruff check .
docker compose run --rm --no-deps api python -m mypy
docker compose run --rm --no-deps api python -m pytest tests/integration/test_r0_recovery.py -q
docker compose run --rm --no-deps api python -m pytest --cov=src/vinami --cov=apps.api --cov=apps.worker --cov-report=term-missing -q
```

Baseline commands and pre-remediation results are preserved in `docs/recovery/r0-baseline.md`.

## Files and migration

New safety/runtime modules: actor context; physician decision domain, ports, application handler, and adapter; closure ports/application/adapter; audit writer port/adapter; schema/ORM registry; R0 regression tests; and the R0 documentation set. Modified modules cover workflow definition/model/engine/persistence, case model/persistence, ECG/troponin provenance, event handlers/dispatcher, unit of work/composition, API readiness, worker startup, Alembic environment, Compose, and static-tool configuration. No frontend styling or page behavior was changed; only a pre-existing dashboard import-order lint finding and mypy source configuration were corrected.

Created migration: `a7d3f0b2c6e1_r0_safety_runtime.py`.

## Remaining defects and limits

- The `/api/v1` clinical vertical slice remains incomplete; R0 intentionally did not implement all routes.
- Identity is a persisted structural authorization placeholder, not authentication.
- The system is a research/engineering MVP and is not clinically validated.
- Demonstration workflow/rules are not for clinical use and contain no approved guideline thresholds.
- Audit is database-trigger protected but not cryptographically tamper-evident.
- Coverage is uneven in unimplemented application modules; 85% aggregate coverage must not be read as feature completeness.
- The TestClient stack emits one deprecation warning, and `apps.worker` is not imported by coverage instrumentation even though worker runtime was verified directly.
- The complete project tree is still untracked by the parent Git repository; create an intentional baseline commit before creating `recovery/r0-safety-runtime`.

## R1 entry condition

Start with one API-driven Patient -> Encounter -> Clinical Case -> Timeline/Audit slice using authenticated actor-context binding. Keep ECG AI replaceable and outside workflow authority. Do not begin broader UI work until that slice passes PostgreSQL, outbox, API-contract, and safety tests end to end.
