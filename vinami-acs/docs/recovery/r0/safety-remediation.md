# R0 Safety Remediation

Status: verified foundation work, not clinical validation.

## Root causes

- `facts_patch` mixed observations with clinical authority.
- Consequential workflow transitions trusted an in-memory boolean instead of a stored decision.
- `ClinicalCase.close()` exposed an aggregate mutation without coordinated workflow, alert, task, outcome, actor, and concurrency checks.
- Actor identity existed only as optional command data and was not checked against persisted roles.

## Remediation

Observational workflow facts remain patchable through a typed allow-list. The authoritative keys `physician_decision_recorded`, pathway approval, cath-lab review approval, and closure approval are rejected at the domain boundary. Consequential commands also reject missing actor, decision, case version, and correlation context at the application boundary.

`PhysicianDecision` is immutable and append-only. It records decision identity, case identity, persisted actor and role, explicit type and status, reason, evidence reference, workflow and case versions, UTC timestamps, and correlation/causation. Corrections and revocations reference an earlier record; a revoked original is no longer effective.

Cath-lab behavior is deliberately a request for physician-led review. AI and ECG data cannot supply the decision port. Case closure is available only through the coordinated closure handler and requires a compatible workflow, two explicit physician decisions, disposition, no urgent unresolved alert, no consequential open task, matching versions, and an idempotency key.

## Evidence

- Domain bypass, missing decision, wrong decision type, revoked decision, AI-only input, actorless command, and stale-version tests pass.
- PostgreSQL integration proves persisted actor authorization and persisted-decision lookup.
- Rejected consequential commands create audit records.

The demonstration workflow remains labelled `Demonstration workflow - not for clinical use.`
