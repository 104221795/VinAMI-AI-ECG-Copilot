# Backend Acceptance Matrix

Acceptance is evaluated as a product backend capability, not as the existence of a similarly named
class. A capability is **working** only when a caller can use a real application/API contract, the
state persists, required events/audit are produced, and safety constraints hold.

| # | Capability | Status | Verified evidence |
|---:|---|---|---|
| 1 | Register patient | Partial | Domain/repository/UoW persisted a patient; `POST /api/v1/patients` is 405; event has no audit handler. |
| 2 | Start encounter | Partial | Domain/repository/UoW persisted an encounter; no command API; event has no audit handler. |
| 3 | Open ACS case | Partial | Domain/repository/UoW persisted a case and outbox event; no command API; projection dead-lettered. |
| 4 | List active cases | Placeholder | `GET /api/v1/clinical-cases` always returns empty, including with one persisted case. |
| 5 | Retrieve case detail | Missing | No by-ID route; runtime returns 404. |
| 6 | Record symptoms | Partial | Domain and pure apply function exist; no repository/UoW/API; `DataStatus` is lost in schema. |
| 7 | Record vitals | Partial | Domain and table exist; no repository/UoW/API. |
| 8 | Create ECG study | Partial | Aggregate/repository/table exist; no upload/application/API/evidence storage. |
| 9 | Request ECG AI analysis | Missing | Port and mock provider exist, but no application pipeline, request event, failure path, timeout, or API. |
| 10 | Retrieve ECG result | Placeholder | Generic empty `GET /api/v1/ecg-ai-results`; no result detail API. |
| 11 | Record serial troponin | Partial | Domain/repository code exists, but no application/API and persistence is lossy. |
| 12 | Retrieve troponin timeline | Placeholder | Generic empty `GET /api/v1/troponin`; no case timeline query. |
| 13 | Generate pathway suggestion | Partial | Demo engine exists internally; no rule registry/application/persistence flow/API/event. |
| 14 | Record physician decision | Failing | No API; workflow accepts a spoofable boolean fact and can have `typed_physician_decision=None`. |
| 15 | Create and complete task | Partial | Task aggregate/repository and workflow effect exist; no application/API; workflow production start fails. |
| 16 | Raise and acknowledge alert | Partial | Alert aggregate/repository exists; no application/API; resolve emits no event. |
| 17 | Retrieve workflow state | Failing | Endpoint is an empty placeholder; internal production workflow creation raises `NoReferencedTableError`. |
| 18 | Retrieve timeline | Failing | Endpoint is empty; `ClinicalCaseOpened.v1` projection dead-lettered and created zero rows. |
| 19 | Retrieve audit trail | Failing | Endpoint is empty; case projection dead-lettered; patient/encounter events publish with zero handlers. |
| 20 | Retrieve model information | Placeholder | Empty collection endpoint; no active-model query or seeded model, despite internal value objects. |

## Totals

| Classification | Count |
|---|---:|
| Working | 0 |
| Partial | 10 |
| Placeholder | 4 |
| Missing | 2 |
| Failing | 4 |
| Untested | 0 |

"Untested" is zero because every capability was classified from source plus runtime/API evidence.
This does not mean every partial implementation has adequate tests.

## API Surface Observed

```text
/api/v1/alerts => GET
/api/v1/audit => GET
/api/v1/clinical-cases => GET
/api/v1/ecg-ai-results => GET
/api/v1/ecg-studies => GET
/api/v1/encounters => GET
/api/v1/model-registry => GET
/api/v1/pathways => GET
/api/v1/patients => GET
/api/v1/tasks => GET
/api/v1/timeline => GET
/api/v1/triage => GET
/api/v1/troponin => GET
/api/v1/vitals => GET
/api/v1/workflows => GET
/health => GET
/ready => GET
```

There are no clinical `POST`, `PUT`, `PATCH`, `DELETE`, detail, action, or upload operations.
