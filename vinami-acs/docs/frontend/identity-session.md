# Identity and Session Boundary

F0 uses the R1.5 identity architecture. The backend remains authoritative. `/api/v1/identity/session` reports the actor derived from the verified provider context; the UI has no actor or role input.

In development, the Next.js server injects one predefined synthetic identity from `VINAMI_WEB_DEVELOPMENT_IDENTITY`. Browser code cannot supply or elevate that value. The header visibly labels both the synthetic actor and `Development identity`. Development mode is rejected when `NEXT_PUBLIC_ENVIRONMENT=production`.

No access token is placed in `localStorage`, public environment variables or Client Component props. Production OIDC and secure HTTP-only session-cookie behavior were not exercised in F0. The provider remains replaceable, and write actions stay outside the R1 slice.

Supported presentation states are loading, verified development session, session unavailable, permission denied and provider unavailable. Correlation IDs are retained in expandable technical details.
