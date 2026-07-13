# R1.5 Validation Report

## Scope

Validation covers identity contracts, development and OIDC providers, permission policy,
FastAPI integration, PostgreSQL identity binding, audit provenance, migration behavior,
R0/R1 regression, and clean Compose runtime. It does not validate a live hospital issuer.

## Targeted Results

- Identity/configuration/architecture tests: 20 passed.
- R1.5 API, R1 lifecycle, migration, and outbox targeted tests: 17 passed.
- Migration downgrade, upgrade, and autogenerate check: passed.
- Raw bearer value persistence test: passed.

## Final Gate

Status: passed for the R1.5 research and engineering scope.

- Ruff format check: 200 Python files formatted.
- Ruff lint: passed.
- mypy strict: 169 source files, no issues.
- pytest: 83 passed, 2 dependency deprecation warnings.
- coverage: 87% across 4,317 statements.
- Alembic downgrade/upgrade/check: passed; head `f19c7a42d8e1`.
- Clean Compose: PostgreSQL, Redis, API, worker, dashboard, and Prometheus started.
- Readiness: PostgreSQL schema ready and development identity mode clearly reported.
- HTTP acceptance: missing identity 401; read-only mutation 403; Patient, Encounter, and
  Clinical Case commands 201; persistent idempotency returned the original Patient.
- Worker acceptance: three lifecycle events published, zero dead letters, three timeline
  rows, and three success audit rows.
- Audit provenance: verified nurse actor, subject, provider, authentication method, and
  applied permissions persisted; untrusted actor headers did not override them.
- Placeholder API resources: anonymous access 401, clinical read-only access 403, explicit
  `system:read` service access 200.

## Defects Fixed During Validation

1. FastAPI could not resolve a dependency-factory forward annotation; the dependency is
   now evaluated under Python 3.12 and OpenAPI generation passes.
2. The R1 downgrade could not restore non-null legacy name columns after R1-created
   patients; downgrade now supplies explicit legacy placeholders before the constraint.
3. Audit indexes existed in migration but not ORM metadata; mappings now match Alembic.
4. Nonclinical placeholder `/api/v1` routes could be read anonymously; they now require
   `system:read` until real use cases replace them.

## Known Limitations

- No live hospital OIDC issuer, enterprise SSO, or hospital directory was configured.
- OIDC readiness proves validated local configuration, not remote JWKS availability or an
  identity-provider service-level objective.
- Resource-aware organization, location, and assigned-team facts exist in the policy
  contract, but the R1 lifecycle resources do not yet expose enough ownership data for
  full scope enforcement.
- The existing Streamlit developer UI was not changed and does not yet supply R1.5
  credentials. A serious client must implement the documented identity flow.
- Two nonblocking dependency warnings remain: Starlette TestClient/httpx deprecation and
  FastAPI's deprecated 422 status constant path.
- This work is not a production deployment, medical device, or clinical-readiness claim.

## Exact Completion Commands

```text
docker compose run --rm --no-deps -v D:\MyNewDesktop\VinStroke\vinami-acs:/workspace -w /workspace api ruff format --check .
docker compose run --rm --no-deps -v D:\MyNewDesktop\VinStroke\vinami-acs:/workspace -w /workspace api ruff check .
docker compose run --rm --no-deps -v D:\MyNewDesktop\VinStroke\vinami-acs:/workspace -w /workspace api mypy
docker compose run --rm --no-deps -v D:\MyNewDesktop\VinStroke\vinami-acs:/workspace -w /workspace api pytest -q --cov=src/vinami --cov=apps/api --cov=apps/worker --cov-report=term
docker compose down -v
docker compose up --build -d
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic check
docker compose up --build -d api
```
