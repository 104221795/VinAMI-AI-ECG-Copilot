# R2 Design: Triage and Vital Documentation

## Scope and Safety

R2 adds factual clinical documentation to an existing suspected-ACS case. It does not diagnose, score risk, interpret vital signs, select a pathway, or apply a clinical threshold. The documentation completeness policy identifies missing fields only.

The slice follows the existing modular-monolith boundaries:

```mermaid
flowchart LR
  UI[Next.js clinical workspace] -->|versioned HTTP DTOs| API[FastAPI router]
  API --> APP[Triage application handlers]
  APP --> DOMAIN[Triage and vital aggregates]
  APP --> UOW[SQLAlchemy unit of work]
  UOW --> DB[(PostgreSQL)]
  UOW --> OUTBOX[Transactional outbox]
  OUTBOX --> PROJECT[Timeline and Audit projectors]
```

## Domain Decisions

- `TriageAssessment` is an append-only aggregate revision. A correction creates a new ID, increments revision/version, references the corrected assessment, and requires a reason.
- `VitalObservationSet` groups observations captured together. Repeated measurement sets increment the sequence; corrections retain the sequence and append a revision.
- `StructuredObservation` distinguishes `present`, `absent`, `unknown`, and `not_assessed`.
- `VitalMeasurement` requires a finite value, UTC timestamp, source, quality declaration, and an explicit unit allowed for its observation kind.
- Closed cases reject routine documentation.
- Command handlers validate the persisted actor, persistent idempotency key, parent case, expected version, and correction target.

## Completeness

Policy `r2-documentation-v1` reports only:

1. Chief complaint not documented.
2. Symptom onset not assessed.
3. No initial vital set.

These are documentation gaps, not clinical abnormalities. Policy evaluation runs in the backend and the frontend renders its output without reimplementing it.

## Command Flow

```mermaid
sequenceDiagram
  participant UI as Next.js
  participant API as FastAPI
  participant H as Command handler
  participant U as Unit of work
  participant DB as PostgreSQL
  participant W as Outbox worker
  UI->>API: POST command + Idempotency-Key
  API->>H: typed command + verified actor
  H->>U: lock idempotency and load case
  H->>U: append documentation + event + response
  U->>DB: one transaction commit
  API-->>UI: 201 persisted response
  W->>DB: claim outbox event
  W->>DB: append Timeline and Audit projections
```

## Prohibited Dependencies

The domain imports no FastAPI, SQLAlchemy, Streamlit, database session, or AI runtime. Next.js imports no Python module, repository, database code, workflow rule, or model runtime. Browser commands pass through an allow-listed same-origin BFF; server configuration supplies the development identity.
