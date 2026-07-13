# API Contract Gaps

## Current Truth

FastAPI exposes health, readiness, metrics, and 15 generic collection GETs. The collection handler
is defined inside one loop in `apps/api/app.py` and never enters a Unit of Work.

No `APIRouter`, clinical Pydantic DTO, dependency-injected command handler, actor context,
permission boundary, or case read model exists.

## Missing Core Contracts

Minimum vertical-slice contracts:

```text
POST /api/v1/patients
GET  /api/v1/patients/{patient_id}
POST /api/v1/encounters
GET  /api/v1/encounters/{encounter_id}
POST /api/v1/clinical-cases
GET  /api/v1/clinical-cases
GET  /api/v1/clinical-cases/{case_id}
```

Clinical evidence/workflow contracts still missing:

```text
POST /api/v1/clinical-cases/{case_id}/symptoms
POST /api/v1/clinical-cases/{case_id}/vitals
POST /api/v1/clinical-cases/{case_id}/ecg-studies
POST /api/v1/ecg-studies/{study_id}/quality-assessments
POST /api/v1/ecg-studies/{study_id}/ai-analyses
GET  /api/v1/ecg-studies/{study_id}/ai-result
POST /api/v1/clinical-cases/{case_id}/troponin/orders
POST /api/v1/troponin/orders/{order_id}/collections
POST /api/v1/troponin/orders/{order_id}/results
GET  /api/v1/clinical-cases/{case_id}/troponin-timeline
POST /api/v1/workflows/{workflow_id}/commands
GET  /api/v1/clinical-cases/{case_id}/workflow
POST /api/v1/clinical-cases/{case_id}/physician-decisions
POST /api/v1/tasks/{task_id}/complete
POST /api/v1/alerts/{alert_id}/acknowledge
POST /api/v1/alerts/{alert_id}/resolve
GET  /api/v1/clinical-cases/{case_id}/timeline
GET  /api/v1/clinical-cases/{case_id}/audit
GET  /api/v1/model-registry/active
```

Endpoint names must be finalized from use-case language before implementation. The list describes
required behavior, not an approved final URL design.

## Cross-Cutting Contract Failures

| Requirement | Status |
|---|---|
| Request/response DTOs | Missing |
| Database-backed pagination | Missing |
| Filtering | Missing |
| Correlation ID response | Partial, works |
| Correlation ID structured logs/events | Missing |
| Actor context | Missing |
| Permission placeholder | Missing |
| Idempotency key | Missing |
| Optimistic concurrency header | Missing |
| UoW per command | Missing |
| RFC 7807 errors | Failing for observed 404/405/422 |
| Provider failure mapping | Missing |
| Workflow safety rejection | Missing |
| Upload validation | Missing |
| No ORM leakage | Vacuously true because no clinical routers exist |

Observed error bodies are FastAPI defaults:

```json
{"detail":"Method Not Allowed"}
{"detail":"Not Found"}
{"detail":[{"type":"greater_than_equal", "loc":["query","page"]}]}
```

They are not RFC 7807 problem documents. The custom `HTTPException` handler does not cover the
observed routing and validation errors.

## Readiness Contract

`/ready` must verify at least:

- PostgreSQL connectivity;
- Alembic revision equals application head;
- required tables exist;
- optionally, outbox/worker health through a separately defined operational contract.

The current response claims ready against an empty schema.

## OpenAPI and Contract Tests

OpenAPI generation itself works, but there are no examples, command schemas, response schemas,
problem schemas, idempotency headers, version headers, or permission annotations. The sole contract
test checks `/health` fields. Schemathesis is not configured.

## Assessment

Sprint 9 API implementation is **not delivered**. The current API is a platform shell.
