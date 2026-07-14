# F0 Baseline

Recorded on 2026-07-13 before F0 implementation.

| Evidence               | Baseline                                                            |
| ---------------------- | ------------------------------------------------------------------- |
| Recoverable checkpoint | `b278803` (`feat: complete R1.5 identity binding foundation`)       |
| F0 branch              | `frontend/f0-nextjs-clinical-slice`                                 |
| Alembic revision       | `f19c7a42d8e1` (head)                                               |
| Pre-F0 OpenAPI SHA-256 | `2ed55fa115005693d42d69d8bb7381a540ee905ee2f2c5beda0c9ac122e8f063`  |
| API base URL           | `http://localhost:8000` locally; `http://api:8000` in Compose       |
| Identity mode          | Controlled development provider; fixed synthetic identities only    |
| Frontend state         | Streamlit developer shell on port 8501 with future placeholder tabs |

Runtime proof: `/ready` returned `ready`; the R1 queue returned one PostgreSQL-backed case; its
case detail, Encounter, Patient, persisted Timeline, and immutable Audit endpoints were readable
with the predefined `physician` development identity. Production OIDC was not configured or
exercised. The baseline is an engineering checkpoint, not clinical or production approval.
