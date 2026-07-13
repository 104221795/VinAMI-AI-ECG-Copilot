# ADR-010: Verified Identity and Permission Boundary

- Status: Accepted for R1.5
- Date: 2026-07-13

## Context

R1 accepted `X-Actor-ID` and `X-Actor-Role` as structurally validated development
provenance. Those headers were not authentication and could not safely authorize a
clinical client. VinAMI needs a replaceable boundary that supports deterministic local
development now and hospital OIDC later without coupling application or domain code to a
token SDK.

## Decision

The API authenticates every R1 lifecycle operation through an `IdentityProvider` port.
The provider returns a framework-free `VerifiedIdentity`. A separate
`AuthorizationPolicy` enforces explicit permissions, and the API constructs
`ActorContext` only from the verified result.

Two adapters are provided:

1. `DevelopmentIdentityProvider` accepts only named, predefined synthetic fixtures and
   is prohibited when the application environment is production.
2. `OIDCIdentityProvider` verifies JWT signatures through JWKS and validates issuer,
   audience, expiry, not-before, and an algorithm allow-list. It stores no token.

The verified provider subject is idempotently bound to a stable actor UUID before an
application command runs. Audit records persist safe identity provenance and the applied
permission. Authentication and authorization failures are separate outcomes.

## Consequences

- Client-supplied actor and role headers are no longer authoritative.
- Routers declare permissions but contain no role matrix.
- OIDC integration can be configured without changing lifecycle use cases.
- Development requests must explicitly select a known synthetic identity.
- OIDC readiness currently reports validated configuration, not a live hospital-provider
  service-level guarantee.
- This foundation is production-shaped but is not a claim of production identity
  integration or clinical readiness.
