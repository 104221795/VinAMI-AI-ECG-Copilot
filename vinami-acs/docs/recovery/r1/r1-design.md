# R1 Design

## Architecture path

FastAPI routers map validated HTTP data to application commands/queries. Command handlers depend on
repository and unit-of-work protocols, validate the development actor reference, claim persistent
idempotency, invoke domain factories, and commit aggregate plus outbox once. SQLAlchemy adapters are
composed only by `AppContainer`. The worker projects committed events to immutable audit and case
timeline rows.

```text
HTTP -> Pydantic DTO -> application handler -> ports/UoW -> domain aggregate
                                               |          -> domain event
                                               +-> PostgreSQL state + idempotency + outbox (one commit)
outbox worker -> idempotent audit/lifecycle timeline projection
```

## Commands

- `RegisterPatient`: unique synthetic/non-sensitive reference, safe demographic summary.
- `StartEncounter`: requires persisted Patient.
- `OpenClinicalCase`: requires persisted Encounter and no active case for that encounter.

All commands carry command ID, `ActorContext`, idempotency key, request timestamp, and payload.
Idempotency scope is `(actor_id, command_type, idempotency_key)`. A PostgreSQL transaction advisory
lock serializes concurrent requests for the same scope. Same key and payload returns the stored DTO;
same key and different payload is a conflict.

## Queries

- Get Patient, Encounter, and Clinical Case by UUID.
- List active cases with deterministic `updated_at DESC, case_id DESC` ordering and filters.
- Get persisted lifecycle timeline and immutable audit for a case.

Queries return application DTOs and never ORM records.

## Events and consistency

R1 uses existing `PatientRegistered.v1`, `EncounterStarted.v1`, and `ClinicalCaseOpened.v1`
envelopes. Actor role and request source travel in event metadata; correlation and causation remain
first-class envelope fields. Aggregate state, persistent idempotency result, and outbox commit
atomically. Audit and timeline are eventually consistent because the internal worker projects them
after commit. API tests execute or poll the projection explicitly.

When a case opens, the lifecycle projection persists patient-registration and encounter-started
entries into that case's timeline, followed by case-opened. Audit remains event-owned and is queried
for the patient, encounter, and case aggregate chain without mutation.

## Data decisions

- Existing patient identifier `(system, value)` is the explicit unique reference policy.
- The R1 API does not collect or return names or exact birth dates; it accepts an optional age band
  and sex-at-birth summary. Legacy nullable name/date fields remain for compatibility.
- One `OPEN` or `UNDER_REVIEW` case is allowed per encounter; PostgreSQL enforces the policy with a
  partial unique index.
- Patient and Encounter gain aggregate version and UTC created/updated timestamps. Clinical Case
  gains UTC `updated_at`.
- Audit remains append-only. R1 adds request source; timeline gains explicit display/provenance
  columns and case-scoped source-event uniqueness.

Actor headers are structurally validated and checked against a persisted development identity
record. This is an authorization placeholder, not production authentication.
