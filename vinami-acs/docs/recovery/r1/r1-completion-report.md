# R1 Completion Report

## Decision

**GO for R1 Foundation Clinical Lifecycle Vertical Slice.** This decision applies only to the
defined engineering slice and is not production or clinical approval.

## Completed capabilities

- Register/get Patient through `/api/v1` using a non-sensitive reference and safe demographics.
- Start/get Encounter only for a persisted Patient.
- Open/get/list suspected ACS Clinical Cases only for persisted Encounters.
- Enforce one active case per Encounter.
- Persist command idempotency and return the original result across process restart.
- Commit lifecycle state, idempotency result, and outbox atomically.
- Project Patient -> Encounter -> Case into a persisted case timeline.
- Query immutable actor-linked lifecycle audit.
- Seed three deterministic synthetic lifecycle cases through application handlers.
- Preserve all R0 physician-decision, cath-lab, closure, provenance, readiness, and audit controls.

## Migration

`d4c8a91e7b32_r1_foundation_lifecycle.py` adds lifecycle versions/timestamps, command idempotency,
active-case uniqueness, request source, and explicit timeline provenance. Clean Compose applied it
automatically and Alembic reported no drift.

## Runtime acceptance

Migration service exited 0; API became healthy; worker started; `/ready` reported R1 head. Seed was
repeatable. Real GETs returned persisted list/detail/timeline/audit data. A separate lifecycle sent
through the POST API was projected by the running worker with zero dead letters. API/worker restart
did not lose data.

## Limitations

- Actor context is structurally validated against a development identity record but is not
  production-authenticated.
- Timeline and audit projection are eventually consistent, not immediate.
- No ECG, AI, troponin, reasoning, pathways, tasks, alerts, notifications, or frontend behavior was
  added by R1.
- Existing non-R1 collection placeholders remain and are not claimed as implemented capabilities.
- The R1 API does not implement production permissions, rate limits, FHIR/HL7 integration, or
  cryptographic audit tamper evidence.
- Dependency warnings listed in `r1-test-report.md` remain non-blocking technical debt.

## R2 recommendation

Build the structured Triage and Vital Signs evidence-capture slice on these contracts. First bind
ActorContext to real authentication/authorization architecture, then add command/query ports,
PostgreSQL persistence, outbox events, timeline/audit projection, and API contracts for symptoms
and vitals. Do not reconnect clinical UI or ECG AI until that evidence slice passes the same clean
runtime and safety gates.

R1 is not production-ready, is not clinically validated, and must not be used for patient-care
decisions.
