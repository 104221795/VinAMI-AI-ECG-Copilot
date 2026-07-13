# Event Catalog

## Versioned Event Envelope

Every emitted event uses a JSON envelope. Payload schemas are versioned independently by `event_type` suffix and are immutable after publication.

```json
{
  "event_id": "uuid",
  "event_type": "ClinicalCaseOpened.v1",
  "event_version": 1,
  "occurred_at": "2026-07-13T00:00:00Z",
  "aggregate_type": "ClinicalCase",
  "aggregate_id": "uuid",
  "aggregate_version": 1,
  "correlation_id": "uuid",
  "causation_id": "uuid-or-null",
  "actor_id": "uuid-or-system",
  "payload": {},
  "metadata": {}
}
```

The envelope is written to the outbox in the same transaction as the aggregate change. Consumers deduplicate by the durable pair `(event_id, handler_name)`, record processing outcome, retry failures, and never silently discard a failure. `event_type` remains compatible with the catalog's `.v1` notation; `event_version` is separately validated by the serializer registry.

## Events

| Event | Producer | Essential payload | Primary consumers |
|---|---|---|---|
| `PatientRegistered.v1` | Patient/Encounter | patient ID, local reference | Audit, case UI projection |
| `EncounterStarted.v1` | Patient/Encounter | encounter ID, patient ID, location | Audit, ACS Case |
| `ClinicalCaseOpened.v1` | ACS Clinical Case | case ID, encounter ID, opening reason | Timeline, task/alert projections |
| `SymptomsRecorded.v1` | Triage | case ID, symptom snapshot reference | Clinical Reasoning, Audit |
| `VitalsRecorded.v1` | Triage | case ID, vital set reference | Clinical Reasoning, Audit |
| `ECGUploaded.v1` | ECG Intelligence | case ID, study ID, input reference | Timeline, ECG quality workflow |
| `ECGQualityAssessed.v1` | ECG Intelligence | study ID, assessment state, assessor | Clinical Reasoning, Audit |
| `AIAnalysisRequested.v1` | ECG Intelligence | analysis ID, study ID, provider request ID | Adapter worker, Audit |
| `AIAnalysisCompleted.v1` | ECG Intelligence | analysis ID, normalized result, model provenance | Clinical Reasoning, Timeline, Model Registry projection |
| `AIAnalysisFailed.v1` | ECG Intelligence | analysis ID, failure code, retryability | Alerts, Timeline |
| `TroponinOrdered.v1` | Troponin Intelligence | case ID, order reference | Timeline |
| `TroponinCollected.v1` | Troponin Intelligence | case ID, collection reference/time | Timeline |
| `TroponinResulted.v1` | Troponin Intelligence | measurement ID, value/unit/time, delta references | Clinical Reasoning, Timeline |
| `RepeatECGRequested.v1` | Workflow and Tasks | case ID, task ID, reason | ECG queue projection, Audit |
| `RepeatECGDue.v1` | Workflow and Tasks | case ID, task ID, due time | Alerts, task queue |
| `ClinicalPathwaySuggested.v1` | Clinical Reasoning | assessment ID, ruleset version, demo statement, conflicts | Workflow, Alerts, Timeline |
| `WorkflowTransitioned.v1` | Workflow and Tasks | case ID, command ID, transition, source/destination state, demonstration notice | Timeline, Audit |
| `PhysicianReviewRequested.v1` | Clinical Reasoning | case ID, reason, assessment ID | Workflow, Alerts |
| `PhysicianDecisionRecorded.v1` | Workflow and Tasks | review ID, physician actor, decision, evidence refs | Audit, case dashboard |
| `TaskCreated.v1` | Workflow and Tasks | task ID, type, assignee, due time | Task queue, Timeline |
| `TaskCompleted.v1` | Workflow and Tasks | task ID, outcome, completing actor | Timeline, Alerts |
| `AlertRaised.v1` | Alerts and Escalation | alert ID, type, source, severity label | Alert queue, Timeline |
| `AlertAcknowledged.v1` | Alerts and Escalation | alert ID, actor, time | Timeline |
| `AlertResolved.v1` | Alerts and Escalation | alert ID, actor, resolution reason, time | Timeline |
| `CathLabReviewRequested.v1` | Workflow and Tasks | case ID, physician confirmation reference, review task ID | Timeline, task queue |
| `TransferRequested.v1` | Workflow and Tasks | case ID, physician confirmation reference, destination reference | Timeline, task queue |
| `CaseClosed.v1` | ACS Clinical Case | case ID, closure reason, actor | Timeline, audit |

`CathLabReviewRequested.v1` is a human-review request only. It cannot represent activation and it must carry the prior physician-confirmation reference.
