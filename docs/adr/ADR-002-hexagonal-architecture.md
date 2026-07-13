# ADR-002: Use Hexagonal Architecture and Dependency Inversion

- **Status:** Accepted
- **Date:** 2026-07-13

## Decision

Each bounded context exposes application inbound ports and depends on outbound port interfaces for persistence, clocks, storage, identity, model providers, and event delivery. Infrastructure adapters implement those interfaces. Domain and application code cannot import delivery/framework/model implementation code.

## Rationale

Clinical workflow needs deterministic tests and must remain independent from PostgreSQL, Streamlit, model runtimes, and external integrations.

## Consequences

- Unit tests use fakes for ports; integration tests exercise adapters separately.
- SQLAlchemy models remain mapping-only and FastAPI routers remain orchestration-free.
- The initial structure is more explicit than a CRUD application, by design.

