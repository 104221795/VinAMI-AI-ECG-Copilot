# R2 Data Model

Migration: `a2c4e6f8b0d1_r2_triage_vitals.py`, additive from `f19c7a42d8e1`.

| Table                            | Ownership | Key constraints                                                                 |
| -------------------------------- | --------- | ------------------------------------------------------------------------------- |
| `triage_assessments`             | Triage    | Unique case/revision; self-FK for correction; actor/case FKs                    |
| `triage_structured_observations` | Triage    | Unique assessment/category/name; explicit state                                 |
| `vital_observation_sets`         | Triage    | Unique case/sequence/revision; self-FK for correction; case/encounter/actor FKs |
| `vital_measurements`             | Triage    | Unique set/kind; explicit value, unit, time, source, quality                    |

All record IDs are UUIDs and timestamps are timezone-aware UTC. Human-readable enums are stored as bounded strings to avoid PostgreSQL enum migration coupling. No JSONB is used for structured clinical observations because their constraints and query ownership are relational.

The previous `symptom_observations` and `vital_observations` tables remain mapped for migration compatibility but are not used by R2 writes. `alembic check` reported no new upgrade operations after migration, proving the change does not propose dropping those legacy tables.

## Append-Only Correction Model

Corrections never update or delete the prior row. The current record is the highest revision. Vital measurements are children of an immutable vital-set revision. The repository explicitly flushes the parent set before child measurements, while aggregate, children, idempotency result, and outbox event remain in one database transaction.
