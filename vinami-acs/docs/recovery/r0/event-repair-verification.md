# Event And Outbox Repair Verification

`ClinicalCaseOpened.v1` now processes through the production mapping registry without `NoReferencedTableError`. Patient and encounter lifecycle events are not silently ignored: each has a registered foundational audit handler; case lifecycle events also project to the case timeline.

The dispatcher retains stored envelopes, delivery attempts, idempotent-consumer records, retry counters, dead-letter state, and replay controls. Replay resets eligible delivery state but unique source-event constraints prevent duplicate audit/timeline projection.

## Runtime probe

One deterministic patient, encounter, and clinical case were committed with their events in the same unit of work. Worker logs recorded one handler for each event. PostgreSQL then showed:

| Evidence | Result |
|---|---:|
| Outbox events | 3 published |
| Delivery attempts | 1 per event |
| Dead letters | 0 |
| Audit records | 3 |
| Case timeline records | 1 |

The rows remained after API, worker, and PostgreSQL restarts. Retry, dead-letter, replay, idempotency, and atomicity remain covered by the existing integration suite.
