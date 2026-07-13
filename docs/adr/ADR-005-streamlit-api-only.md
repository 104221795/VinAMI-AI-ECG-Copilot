# ADR-005: Keep Streamlit API-Only

- **Status:** Accepted
- **Date:** 2026-07-13

## Decision

The future ACS Streamlit UI is a delivery client that communicates solely through versioned FastAPI endpoints. It performs display, local form state, request submission, and API error presentation only.

## Rationale

The existing VinStroke Streamlit prototype accesses research artifacts directly. Reusing that pattern for ACS would make the UI an untestable clinical decision layer and create a second system of record.

## Consequences

- Streamlit does not import SQLAlchemy, repositories, aggregates, clinical policies, or AI providers.
- API responses expose explicit safety labels and user-actionable structured errors.
- The existing VinStroke UI remains independent rather than being converted in place.

