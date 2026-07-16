# R4 API Contract

All routes use `/api/v1`. Reads require `troponin:read`. Writes require controlled development identity, `X-Correlation-ID`, `Idempotency-Key`, actor context and a version precondition in the body. Development identity is not production authentication.

| Capability              | Route                                                               |
| ----------------------- | ------------------------------------------------------------------- |
| Record/list result      | `POST/GET /clinical-cases/{case_id}/troponin-results`               |
| Read result             | `GET /troponin-results/{result_id}`                                 |
| Amend result            | `POST /troponin-results/{result_id}/amendments`                     |
| Series/deltas/workspace | `GET /clinical-cases/{case_id}/troponin-{series,deltas,workspace}`  |
| Import/list imports     | `POST/GET /clinical-cases/{case_id}/troponin-imports`               |
| Import job/retry        | `GET /laboratory-import-jobs/{job_id}`, `POST .../{job_id}/retry`   |
| Assay catalog           | `GET /troponin-assays`, `GET /troponin-assays/{assay_id}`           |
| Connector/health        | `GET /laboratory-connectors`, `GET .../{connector_id}/health`       |
| Clinician review        | `POST/GET /clinical-cases/{case_id}/troponin-reviews`               |
| Review correction       | `POST /clinical-cases/{case_id}/troponin-reviews/{review_id}/corrections` |
| Repeat requests         | `GET /clinical-cases/{case_id}/repeat-troponin-requests`            |
| Repeat transitions      | `POST /repeat-troponin-requests/{id}/{acknowledge,complete,cancel}` |

Errors use the repository RFC 7807 shape with a safe detail and correlation ID. Unsupported, missing and malformed troponin units return HTTP 422 with an `errors` item for the `unit` field and a typed code such as `unsupported_unit` or `unit_required`. State and idempotency conflicts remain HTTP 409. Connector failures remain persisted on the import job.

OpenAPI snapshot checksum after R4.1: `452b381d31460591fab9fd6cf262d9a1084445bc1314d2e3046a5691028f8fd1`.
