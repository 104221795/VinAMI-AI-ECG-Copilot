# R2 Baseline

Recorded on 2026-07-14 before R2 implementation.

| Evidence             | Baseline                                                                                 |
| -------------------- | ---------------------------------------------------------------------------------------- |
| Branch / checkpoint  | `frontend/f0-nextjs-clinical-slice` / `b278803`                                          |
| Worktree             | F0 changes are present and intentionally preserved                                       |
| Alembic revision     | `f19c7a42d8e1` (head before R2)                                                          |
| Identity             | Controlled predefined development identities; production authentication not exercised    |
| API readiness        | `ready`, PostgreSQL schema healthy                                                       |
| R1 runtime           | 4 persisted cases; case detail, Timeline and immutable Audit readable                    |
| Next.js              | Existing F0 production build health returned HTTP 200 on port 3000                       |
| Existing triage code | Preliminary aggregate and flat observation mappings; no R1 UoW/API/outbox vertical slice |

R2 will add a non-diagnostic documentation slice without changing the deferred F0 clean-Docker classification. No database volume reset or Streamlit migration is permitted in R2.
