# R0 Recovery Baseline

Recorded at: 2026-07-13, Asia/Saigon

This baseline records the repository and runtime state before R0 safety/runtime remediation.
It is evidence for change control, not a production-readiness statement.

## Source State

| Item | Baseline |
|---|---|
| Git commit | `04bd85913bfbf0d0e59bcb915e9ed457ed72e991` |
| Git branch | `main` |
| Project tracking state | `vinami-acs/` and existing architecture/report outputs are untracked from the root repository |
| Recommended recovery branch | `recovery/r0-safety-runtime` |

The recommended branch was not created automatically because the complete `vinami-acs/` tree is
currently untracked. Branching before establishing an intentional project commit would not provide
meaningful change isolation.

## Database State

| Item | Baseline |
|---|---|
| Alembic current/head | `f5a9c2d6e4b1` |
| Public PostgreSQL tables | 28 |
| Outbox published | 2 |
| Outbox dead-letter | 1 |
| Dead-letter event | `ClinicalCaseOpened.v1` from the truth-audit probe |

The current schema reached head only after a manual `alembic upgrade head` during the truth audit.
Clean Compose startup did not apply migrations.

## Test And Static Baseline

```text
pytest: 45 passed, 1 warning
ruff check: failed, 1 dashboard import-order error
mypy: failed, 9 dashboard import-resolution errors
alembic check: failed, 2 migration/metadata constraint differences
```

The two Alembic differences are `uq_alert_workflow_effect` and
`uq_clinical_task_workflow_effect`, present in the migration but absent from ORM table metadata.

## Docker Image And Service Baseline

| Service | Image | Image ID | Baseline state |
|---|---|---|---|
| API | `vinami-acs-api:latest` | `c00aa604c749` | Up, health endpoint healthy |
| Worker | `vinami-acs-worker:latest` | `a978e2620321` | Up after manual migration/restart |
| Dashboard | `vinami-acs-dashboard:latest` | `4e78fdee9be8` | Up |
| PostgreSQL | `postgres:16-alpine` | `e013e867e712` | Up/healthy |
| Redis | `redis:7-alpine` | `6ab0b6e73817` | Up/healthy |
| Prometheus | `prom/prometheus:v2.54.1` | `f6639335d34a` | Up |

These running states do not prove clean startup. At baseline, the API and worker depended on a
manually migrated database, readiness checked only `SELECT 1`, and the worker had previously failed
on missing workflow tables and PostgreSQL restart.

## Baseline Commands

```powershell
git rev-parse HEAD
git branch --show-current
git status --short
docker compose ps -a
docker compose images
docker compose exec -T api alembic current
docker compose exec -T postgres psql -U vinami -d vinami_acs -c "SELECT count(*) AS public_tables FROM pg_tables WHERE schemaname='public'; SELECT version_num FROM alembic_version; SELECT status, count(*) FROM outbox_events GROUP BY status ORDER BY status;"
docker compose exec -T api pytest -q
docker compose exec -T api ruff check apps src tests scripts
docker compose exec -T api mypy apps src scripts
docker compose exec -T api alembic check
```

## Safety Baseline

- `facts_patch` can set `physician_decision_recorded=true`.
- An actorless workflow can reach `CATH_LAB_REVIEW` without a persisted decision.
- `ClinicalCase.close()` can bypass workflow, task, alert, decision, and disposition checks.
- ECG and troponin persistence drops required source/model/assay provenance.
- Production ORM initialization depends on import order and differs from integration fixtures.

