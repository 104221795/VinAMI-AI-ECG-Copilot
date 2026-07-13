# ADR-008: Internal Dispatcher with Idempotent Consumer Ledger

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

ADR-003 established transactional outbox storage but did not define delivery, schema evolution, retry, replay, or handler idempotency. The modular-monolith MVP requires reliable local event reactions without introducing Kafka or distributed infrastructure.

## Decision

Use a versioned `EventEnvelope`, serializer registry, PostgreSQL-backed internal dispatcher, and dependency-injected handlers. Store delivery status, lease timestamps, retry metadata, correlation/causation/actor provenance, and metadata on `outbox_events`. Store successful handler completion in `event_consumptions` with a unique `(event_id, handler_name)` constraint.

Handler execution, projection writes, consumer completion, and the `published` state commit in one local transaction. Handler failure rolls back that transaction and a separate transaction persists retry or dead-letter state. Replay is an explicit CLI operation scoped by event type and UTC time range.

## Consequences

- Delivery is at-least-once, but completed handlers are idempotent.
- Poison events remain inspectable in `dead_letter` status after configured retries.
- The worker can restart or lose a lease without losing committed events.
- Initial handlers are projection-only and cannot cause clinical workflow actions.
- A future broker adapter can replace delivery transport while retaining envelope, registry, outbox, and handler contracts.
