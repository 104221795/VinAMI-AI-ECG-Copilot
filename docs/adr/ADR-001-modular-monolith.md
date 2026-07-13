# ADR-001: Use a Modular Monolith for the MVP

- **Status:** Accepted
- **Date:** 2026-07-13

## Decision

VinAMI ACS will ship as one deployable modular monolith with explicit bounded contexts, ports/adapters, PostgreSQL, and an in-process transactional outbox dispatcher. Context boundaries are contractual so that a future service extraction can replace an adapter or delivery channel without rewriting domain behavior.

## Rationale

The MVP has no demonstrated requirement for independent scaling, independent deployability, Kafka, Kubernetes, or distributed transactions. A single deployable unit lowers operational risk while maintaining boundaries that prevent a future big-ball-of-mud application.

## Consequences

- Cross-context interactions are versioned events/DTOs inside one codebase and one database transaction boundary.
- Schema ownership is per context even when PostgreSQL is shared.
- Microservices are deferred until a concrete load, ownership, security, or deployment need is documented in a new ADR.

