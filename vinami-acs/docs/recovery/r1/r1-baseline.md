# R1 Baseline

Recorded: 2026-07-13, Asia/Saigon. This is a change-control snapshot, not a readiness claim.

| Item | Baseline |
|---|---|
| Commit | `3221f4e62ec84b668e4171031db4f343fe6af5c6` |
| Branch | `recovery/r1-foundation-slice` |
| Worktree | Clean and tracked |
| Alembic | `a7d3f0b2c6e1 (head)` |
| Tests | 55 passed, one Starlette TestClient deprecation warning |
| Compose | PostgreSQL/Redis/API healthy; worker/dashboard/Prometheus up; migrate exited 0 |
| API contract | Platform endpoints plus empty clinical collection placeholders |

The running API container referenced an untagged image digest that was no longer present in the
local image store, so `docker compose images` could not complete. The container remained healthy;
R1 final validation must replace it with a clean reproducible build.

Baseline commands:

```powershell
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
git status --short
docker compose ps -a
docker compose images
docker compose exec -T api alembic current
docker compose run --rm --no-deps api python -m pytest -q
```
