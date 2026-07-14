# F0/R2 Frontend Architecture

## Purpose

F0 is a Next.js App Router client for the verified R1 lifecycle only. The browser never accesses PostgreSQL, Python domain modules, workflow rules, or model runtimes.

```mermaid
flowchart LR
  Browser[Browser and React Client Components] -->|same-origin GET| BFF[Next.js approved BFF routes]
  RSC[Next.js Server Components] --> Adapter[Application API adapter]
  BFF -->|verified development identity and correlation ID| API[FastAPI /api/v1]
  Adapter --> API
  API --> DB[(PostgreSQL system of record)]
  API --> Outbox[Transactional outbox projections]
```

## Boundaries

- `app/` owns routing, composition, route-level loading and failure boundaries.
- `features/` owns user-facing R1 use cases and transport-to-view mapping.
- `entities/` owns presentation models, not backend domain entities.
- `widgets/` owns stable page composition such as the clinical shell.
- `shared/` owns framework adapters, validation, formatting, query policy and reusable presentation behavior.
- `packages/contracts` is generated from the canonical FastAPI OpenAPI snapshot.
- `packages/api-client` wraps generated contracts with timeout, safe GET retry, RFC 7807 mapping and correlation IDs.
- `packages/ui` owns token-driven, side-effect-free primitives.

All application routes are dynamically rendered so actor-specific identity and clinical records are not embedded during image build. TanStack Query owns interactive server state; local React state owns filters and row selection. Runtime Zod validation rejects malformed responses before rendering.

R2 adds `entities/clinical-documentation` and `features/clinical-documentation`. The server feature loads the backend summary and immutable histories; the Client Component owns form state and invokes only generated API-client methods. Four POST paths are separately allow-listed by the BFF. The browser supplies idempotency and correlation references but never supplies a trusted actor identity.

## Enforced Rules

Architecture tests prohibit Python/ORM/model imports, server-only imports from Client Components, local-storage access tokens, future clinical routes and prohibited autonomous clinical claims in production UI source.
