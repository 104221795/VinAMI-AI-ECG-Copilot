# ADR-003: Use a Transactional Outbox for Domain Events

- **Status:** Accepted
- **Date:** 2026-07-13

## Decision

Every committed aggregate mutation that emits a domain event writes a versioned envelope to an outbox table within the same PostgreSQL transaction. A dispatcher claims, delivers, retries, and records structured failures. Event handlers are idempotent by `event_id`.

## Rationale

Writing business data and then publishing an event separately can lose audit/timeline/task/alert updates. A transactional outbox protects the local atomic boundary without introducing a broker.

## Consequences

- Event delivery is at-least-once, so handlers must deduplicate.
- Failed handlers are observable and retried; they are never silently ignored.
- A later external broker can be attached as an additional outbox consumer without altering aggregate behavior.

