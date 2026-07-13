# Non-Functional Requirements

| Area | MVP requirement | Verification approach |
|---|---|---|
| Safety | Explicit demo-rule label; no rule-out/activation path; physician confirmation gate | Unit and API contract tests |
| Auditability | Every mutation/event carries UUID, actor, UTC time, correlation ID and aggregate version | Database integration tests |
| Reliability | Atomic aggregate/outbox write; idempotent handlers; structured retry/failure state | Transaction and handler tests |
| Security | No credentials in repo/logs; API authorization boundary; least-privilege DB account in Compose | Config scan and integration tests |
| Privacy | Minimal data capture; no restricted clinical data in logs; evidence references have provenance | Logging and export tests |
| Performance | Case dashboard and normal mock commands target responsive local development use; no clinical latency claim | Measured dev smoke test with documented environment |
| Availability | Health/readiness endpoints; UI reports unavailable dependencies clearly | Compose health checks |
| Maintainability | Ruff, mypy, pytest, pre-commit, migration discipline, public-interface docstrings | CI/local quality commands |
| Interoperability | Versioned JSON API/event contracts; adapters isolate EHR/LIS/AI/storage | Contract tests |
| Reproducibility | Deterministic seed data; configuration/ruleset/model versions persisted | Seed and provenance tests |

No numerical clinical performance, safety, availability, or diagnostic target is claimed for this research MVP.

