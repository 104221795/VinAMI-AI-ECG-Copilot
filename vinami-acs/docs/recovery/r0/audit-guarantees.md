# Audit Guarantees

Audit persistence is append-only through `SQLAlchemyAuditWriter`; it exposes no update or delete operation. Records capture actor ID and role, action, aggregate type/ID, prior and resulting versions, reason, correlation and causation IDs, accepted/rejected outcome, and UTC timestamp.

Foundational event projections create audit entries using the immutable event envelope. Consequential decision, workflow, and closure handlers explicitly audit accepted or rejected outcomes. Case lifecycle events also create timeline entries linked by source event ID.

PostgreSQL migration `a7d3f0b2c6e1` installs a trigger that rejects `UPDATE` and `DELETE` on `audit_logs`. Integration tests prove both database operations fail and roll back. Unique source-event IDs make event projections idempotent.

Limit: a database owner can disable triggers; production-grade tamper evidence, retention, export signing, and privileged-administrator monitoring are not implemented.
