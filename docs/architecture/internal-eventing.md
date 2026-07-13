# Internal Eventing and Transactional Outbox

## Scope

Sprint 4 implements the MVP's replaceable in-process event transport. It uses PostgreSQL for durable storage and delivery state. Domain code does not import the dispatcher, SQLAlchemy, Redis, Kafka, or any model runtime.

## Envelope

Every event is an immutable `EventEnvelope` with `event_id`, `event_type`, `event_version`, aggregate identity/version, UTC occurrence time, correlation ID, optional causation and actor IDs, payload, and metadata. Event types retain the approved catalog notation such as `ClinicalCaseOpened.v1`; `event_version` is independently persisted for serializer compatibility checks.

`EventContext` is supplied by a command or consumed message and is propagated by `AggregateRoot._record_event`. A new root context receives a UUID correlation ID. Child work can preserve it and set the causing event ID.

## Delivery

1. Unit of Work writes the aggregate change and its outbox envelope in one PostgreSQL transaction.
2. The worker polls due `pending` rows and uses `FOR UPDATE SKIP LOCKED` when it loads each record.
3. The dispatcher deserializes through `EventRegistry`, invokes registered handlers in the same local transaction, and records a unique `(event_id, handler_name)` consumer ledger entry only after success.
4. The outbox row moves to `published` only when all handlers succeed. Handler writes and completion ledger entries roll back together on failure.
5. A separate failure transaction increments attempts and returns the event to `pending`, or marks it `dead_letter` after `VINAMI_EVENT_MAX_RETRIES` attempts. Failed events are retained with `last_error`.

The semantics are at-least-once. A duplicate delivery cannot repeat a completed handler because of the consumer ledger. The initial handlers create only idempotent audit/timeline projections; they do not create clinical tasks, alerts, decisions, or any autonomous action.

## Registered MVP Handlers

The composition root registers audit/timeline projection handlers for:

- `ClinicalCaseOpened.v1`
- `ECGUploaded.v1`
- `AIAnalysisCompleted.v1`
- `TroponinResulted.v1`
- `RepeatECGDue.v1`
- `ClinicalPathwaySuggested.v1`
- `PhysicianDecisionRecorded.v1`
- `TaskCreated.v1`
- `AlertRaised.v1`
- `CaseClosed.v1`

Events without a handler are still safely marked published after schema validation. This permits catalog growth without coupling all contexts to every projection.

## Replay

Replay is explicit and limited by event type and timezone-aware time range:

```text
make replay REPLAY_ARGS='--event-type ClinicalCaseOpened.v1 --start 2026-07-13T00:00:00+00:00 --end 2026-07-13T23:59:59+00:00'
```

Replay resets only the selected outbox rows and their consumer ledger entries. Source-event unique keys on audit/timeline projections prevent duplicate projection rows during replay.

## Future Broker Boundary

`EventSerializer`, `EventRegistry`, `EventEnvelope`, and handler contracts are transport-neutral. A future Kafka, NATS, or cloud-bus publisher can consume `outbox_events` or use the serializer without changing aggregate behavior or application use cases.
