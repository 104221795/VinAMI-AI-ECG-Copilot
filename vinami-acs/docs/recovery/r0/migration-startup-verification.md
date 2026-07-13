# Migration And Startup Verification

## Startup graph

PostgreSQL healthy -> `migrate` runs `alembic upgrade head && alembic check` -> API and worker start -> API `/ready` validates connectivity, critical tables, and exact revision.

Compose uses `service_completed_successfully` for the migration dependency. API health checks `/ready`; PostgreSQL, Redis, API, and worker have explicit health/restart behavior appropriate to this research MVP.

## Clean-run evidence

The environment was removed with volumes and rebuilt without a manual migration command. Migration logs applied all revisions through `a7d3f0b2c6e1`; the migration service exited `0`; API became healthy; worker started. The first long `up --build -d` caller timed out while Docker was still building, so `docker compose up -d` was used only to wait for/converge the same Compose graph, not to apply migrations manually.

After API, worker, and PostgreSQL restarts:

- `/ready` returned HTTP 200 and revision `a7d3f0b2c6e1`;
- `alembic current` reported head;
- `alembic check` reported no new upgrade operations;
- persisted patient, encounter, case, outbox, audit, and timeline rows remained.

Contract tests also prove readiness returns 503 for a reachable database whose required schema/revision is absent, then 200 after the real migration path.
