# ADR-007: PostgreSQL System of Record and Relational Evidence Model

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

The ACS MVP needs a durable system of record before API or dashboard workflows are added. It must preserve patient, case, evidence, human-decision, audit, and model-provenance facts while keeping the domain independent from ORM code.

## Decision

Use PostgreSQL with SQLAlchemy 2 mappings in bounded-context infrastructure adapters. Keep aggregate behavior in framework-free dataclasses. Use UUID primary keys, UTC timestamps, explicit foreign keys, named PostgreSQL enums, indexes for case/timeline queries, and optimistic versions on `ClinicalCase` and `ClinicalWorkflow`.

Use relational tables for repeated clinical facts and relationships. Use JSONB only for versioned event/audit payloads and genuinely variable evidence metadata. Stage domain events as transactional-outbox rows in the same Unit of Work commit.

The initial Alembic migration includes a complete downgrade, including named enum cleanup.

## Consequences

- Persistence supports actual aggregate behavior without a generic CRUD service layer.
- PostgreSQL integration tests can prove integrity, rollback, concurrency, and migration reversibility.
- The current worker does not dispatch outbox rows; event delivery is a later sprint.
- No table or repository implements clinical thresholds, rule-out behavior, cath-lab activation, or model runtime execution.
