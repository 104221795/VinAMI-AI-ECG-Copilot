# API Client and Contract Control

`pnpm api:snapshot` obtains the real FastAPI schema, recursively sorts it, writes canonical JSON and records SHA-256. `pnpm api:generate` creates `packages/contracts/src/generated.ts` with `openapi-typescript`. Generated files and the OpenAPI snapshot are excluded from Prettier and must not be edited manually.

`pnpm api:check` verifies both the schema checksum and a newly generated client byte-for-byte. Current R2 checksum: `08bface127096fcb088b677b1de76b1fd9c2521e076112ce0096b95b5eeeeefe`.

The `VinamiApiClient` adapter provides typed methods, bounded timeout, one retry for safe GET responses only, RFC 7807 error mapping, correlation-ID extraction and an observability callback. Consequential POST retries are not implemented. Zod schemas independently validate browser/runtime payloads. Unknown values map to explicit unknown presentation rather than crashing the UI.

The browser calls only the same-origin `/api/backend` BFF. Its GET allow-list contains health, identity, lifecycle, triage, and vital resources. Four POST patterns are separately allow-listed for R2 record/correct commands; all require an explicit idempotency key. The key is retained across a failed retry and rotated only after success or reopening an editor. The BFF injects the configured non-production identity server-side and does not expose a generic backend proxy.
