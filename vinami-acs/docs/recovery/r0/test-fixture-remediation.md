# Test Fixture Remediation

Integration tests now initialize ORM mappings through `initialize_mappings()`, the same path used by the production composition root and Alembic. PostgreSQL persistence tests use the real SQLAlchemy adapters, real migrations, constraints, JSONB, triggers, and transactions. No test-only import list is used to hide mapping defects.

R0 regression coverage includes:

- generic authoritative `facts_patch` rejection;
- missing, unauthorized, wrong-type, revoked, AI-only, and stale decision guards;
- append-only revocation invalidating an earlier active decision;
- coordinated closure and critical-alert blocking;
- production composition smoke test;
- readiness before and after schema migration;
- ECG and troponin provenance round trip;
- `ClinicalCaseOpened.v1` audit/timeline handling;
- audit immutability;
- migration upgrade/downgrade and Alembic drift;
- outbox atomicity, retry, dead-letter, replay, and idempotency.

Final suite: 55 passed with one upstream Starlette TestClient deprecation warning. The warning is non-blocking but should be removed when the FastAPI/Starlette test stack is upgraded.
