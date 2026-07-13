# R1.5 Endpoint Permission Matrix

| Method | Path | Required permission |
|---|---|---|
| POST | `/api/v1/patients` | `patient:create` |
| GET | `/api/v1/patients/{patient_id}` | `patient:read` |
| POST | `/api/v1/encounters` | `encounter:create` |
| GET | `/api/v1/encounters/{encounter_id}` | `encounter:read` |
| POST | `/api/v1/clinical-cases` | `clinical_case:create` |
| GET | `/api/v1/clinical-cases` | `clinical_case:read` |
| GET | `/api/v1/clinical-cases/{case_id}` | `clinical_case:read` |
| GET | `/api/v1/clinical-cases/{case_id}/timeline` | `timeline:read` |
| GET | `/api/v1/clinical-cases/{case_id}/audit` | `audit:read` |

Authentication failures return RFC 7807 status 401 and `WWW-Authenticate: Bearer`.
Authorization failures return RFC 7807 status 403. Both include a correlation ID and are
recorded as distinct audit outcomes without credentials.

## Development Fixtures

| Fixture | Lifecycle mutation | Lifecycle read | Audit read | System/identity inspect |
|---|---:|---:|---:|---:|
| `physician` | Yes | Yes | Yes | No |
| `nurse` | Yes | Yes | No | No |
| `technician` | No | Yes | No | No |
| `care_coordinator` | Yes | Yes | No | No |
| `administrator` | Yes | Yes | Yes | Yes |
| `auditor` | No | Yes | Yes | Yes |
| `system_service` | Yes | Yes | Yes | Yes |
| `read_only_reviewer` | No | Yes | No | No |

Fixtures are synthetic and deterministic. They are not hospital users and must not be
enabled in production.
