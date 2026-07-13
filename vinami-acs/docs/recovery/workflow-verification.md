# Workflow Verification

## Implemented Design

The workflow is a versioned JSON-defined state machine with typed states, transitions, guards,
effects, due timers, deterministic task/alert IDs, command receipts, transition history, and
optimistic versioning. It avoids a long clinical `if/else` tree. Unit and PostgreSQL tests cover
normal review, poor ECG quality, rising troponin, conflict, repeat ECG overdue, transfer,
idempotency, stale versions, timer completion, and persistence effects.

This structure is worth preserving.

## Production Runtime Failure

Starting a workflow through `WorkflowCommandHandler` and the normal `AppContainer` failed before
the first transition:

```text
NoReferencedTableError:
clinical_workflows.decision_actor_id -> clinical_users.id
```

The transaction rolled back completely:

```text
clinical_workflows=0
clinical_tasks=0
alerts=0
```

Integration tests pass because their Alembic fixture loads all ORM mappings in the same process
before repositories run. Production composition does not.

## Physician Confirmation Safety Failure

The configured workflow guard checks `WorkflowFacts.physician_decision_recorded`. The public
`WorkflowCommand` accepts an arbitrary `facts_patch`, so the caller controls the guard fact.

An executed domain proof used `actor_id=None`, set the boolean fact, and then requested cath-lab
review. Result:

```text
state=CATH_LAB_REVIEW
typed_physician_decision=None
actorless_transitions=8
```

This does not activate a cath lab, but it violates the charter requirement that consequential
clinical actions require physician confirmation. The state name and generated review task are
still consequential workflow outputs and must be actor-provenanced.

Required correction:

- distinguish caller-supplied observations from system-owned safety facts;
- prevent generic patches from changing `physician_decision_recorded`, critical-alert count,
  evidence conflict, and derived troponin state;
- implement a dedicated `RecordPhysicianDecision` application command that validates actor context,
  persists a typed decision, and derives the workflow fact;
- require the typed persisted decision in cath-lab/transfer/discharge guards.

## Case Closure Safety Failure

`ClinicalCase.close()` is a separate path. It requires only:

- case state `UNDER_REVIEW`;
- expected aggregate version;
- non-empty reason and an arbitrary actor UUID.

It does not verify workflow state, troponin availability, physician role/decision, or unresolved
critical alerts. No application coordinator exists to make the stronger workflow guard
authoritative. The current domain therefore has two inconsistent closure authorities.

## Other Gaps

- Workflow commands have no API, idempotency header, expected-version HTTP contract, or actor
  permission boundary.
- Workflow inputs are not derived from persisted ECG/troponin/triage records.
- `record_physician_decision` in the configured graph does not call
  `ClinicalWorkflow.record_physician_decision()`.
- Repeat ECG is a task/timer only; there is no Dynamic ECG evidence sequence.
- The demonstration notice contains mojibake (`â€”`) in code/config/docs and is not the canonical
  safety label.
- Timer worker has no repeated reminder policy and exits on transient database interruption.
- Compensation transitions exist only for observation/pathway states and have no application/API
  authorization or reason payload.

## Assessment

Workflow model and testability: **good internal foundation**.

Production executability: **failing**.

Human-in-the-loop safety: **blocking failure**.

API/product integration: **missing**.
