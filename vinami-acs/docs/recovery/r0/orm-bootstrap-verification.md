# ORM Bootstrap Verification

`initialize_mappings()` is the single production registry entry point. It imports every concrete mapping, including physician decisions, and calls SQLAlchemy mapper configuration before returning metadata.

The FastAPI/worker composition root, Alembic environment, and integration fixture all use this same function. Tests no longer rely on incidental imports to populate metadata. The production smoke test constructs `AppContainer`, verifies critical tables, configures all relationships, and runs the database readiness probe.

Verified outcomes:

- no `NoReferencedTableError`;
- metadata includes patients, encounters, cases, workflows, decisions, audit, timeline, and outbox;
- API and worker initialize the same registry;
- cyclic closure references use named deferred foreign keys rather than import-order behavior.

This verifies mapping composition, not every future relationship or API use case.
