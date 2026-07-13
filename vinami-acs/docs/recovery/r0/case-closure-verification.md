# Case Closure Verification

## Coordinated command

`CloseClinicalCaseHandler` is the only supported closure path. It validates the workflow and case in one unit of work, then commits the workflow transition, case state, events, and outbox atomically.

Required inputs are actor context, idempotency key, expected case and workflow versions, closure reason, explicit outcome ID, discharge-review decision ID, closure-approval decision ID, and correlation context.

## Blocking conditions

Closure fails when any of the following is true:

- workflow is not at the configured discharge/closure state;
- persisted physician authority is missing, mismatched, stale, revoked, or unauthorized;
- a critical or urgent alert is unresolved;
- a consequential task is open;
- disposition/outcome is missing;
- case or workflow version is stale.

`ClinicalCase.close()` now accepts a validated `CaseClosureAuthorization` value object, so callers cannot perform a bare state flip. The PostgreSQL integration test demonstrates no partial workflow/case change after a failed closure and successful coordinated closure only after the critical alert is resolved.

No real clinical threshold or AMI rule-out claim is introduced.
