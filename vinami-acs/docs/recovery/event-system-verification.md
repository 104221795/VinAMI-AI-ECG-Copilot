# Event System Verification

## Implemented Foundation

The repository has a real `EventEnvelope`, schema registry, serializer, outbox table, consumer
ledger, retry/dead-letter fields, dispatcher, replay command, and structured event logs.

Internal PostgreSQL tests verify:

- aggregate/outbox atomic commit;
- envelope version and provenance serialization;
- duplicate handler idempotency;
- retry and dead-letter state;
- selected replay with a synthetic successful handler.

These mechanics are useful and should be retained.

## Runtime Atomicity Proof

A patient, encounter, and clinical case were committed through one Unit of Work with their three
events. PostgreSQL contained all three aggregate rows and all three outbox rows. This proves the
local write/outbox atomic path for that graph.

However, the command did not propagate one `EventContext`:

```text
events=3
distinct_correlations=3
actorless_events=3
```

The event infrastructure supports context, but product application handlers do not exist to supply
HTTP correlation, causation, and actor identity.

## Runtime Delivery Result

Observed outbox state after the worker ran:

| Event | Handler count/result | Final status |
|---|---|---|
| `PatientRegistered.v1` | No registered handler | published |
| `EncounterStarted.v1` | No registered handler | published |
| `ClinicalCaseOpened.v1` | Audit/timeline handler failed | dead_letter |

The case event failed three attempts with:

```text
NoReferencedTableError: audit_logs.actor_id could not resolve clinical_users.id
```

Consequences:

- `audit_logs=0`;
- `timeline_events=0`;
- accepted patient and encounter actions are not audited because events with no handler are treated
  as successfully published;
- the case event is retained, which is preferable to silent loss, but the product audit guarantee
  is not met.

## Replay

The replay CLI selected and reset the dead-letter event:

```text
replayed=1
```

The worker immediately failed it again. `delivery_attempts` was not reset by replay, increasing from
3 to 4 before returning to dead-letter. Replay selection works, but recovery does not restore a full
retry budget and cannot overcome the production mapping failure.

## Worker Reliability

- Clean startup: worker exits because migrations are absent.
- After manual migration: worker starts.
- PostgreSQL-only restart: worker exits with `OperationalError`/host resolution failure.
- Compose has no worker healthcheck and no restart policy.
- Event-handler failure metrics are absent; only structured logs and row state expose failure.

## Handler Coverage

The default registry projects 11 event types. It does not provide an audit handler for every event
in the catalog. In particular, patient, encounter, symptoms, vitals, quality assessment, analysis
request/failure, troponin order/collection, task completion, alert acknowledgement/resolution,
transfer, and cath-lab review events can be marked published without an audit projection.

## Assessment

| Property | Status |
|---|---|
| Envelope and serializer | Working internally |
| Transactional write | Working for verified aggregate graph |
| Retry/dead-letter persistence | Working mechanically |
| Consumer idempotency | Tested with synthetic handler |
| Default product handlers | Failing in runtime |
| Audit completeness | Failing |
| Correlation/actor propagation | Missing at product boundary |
| Replay recovery | Partial |
| Worker resilience | Failing |

The event system is a reusable foundation, not a reliable product event path in its current state.
