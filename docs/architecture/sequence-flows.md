# Sequence Flows

## Patient Arrival to Clinical Review

```mermaid
sequenceDiagram
  actor Nurse
  actor Physician
  participant UI as Streamlit UI
  participant API as FastAPI API
  participant PE as Patient/Encounter
  participant Case as ACS Case
  participant Audit as Outbox/Audit
  Nurse->>UI: Register patient and start encounter
  UI->>API: POST /api/v1/patients, /encounters
  API->>PE: RegisterPatient / StartEncounter
  PE->>Audit: PatientRegistered.v1, EncounterStarted.v1
  Nurse->>UI: Open suspected ACS case
  UI->>API: POST /api/v1/clinical-cases
  API->>Case: OpenClinicalCase
  Case->>Audit: ClinicalCaseOpened.v1
  Nurse->>UI: Record symptoms and vitals
  UI->>API: POST triage commands
  API->>Audit: SymptomsRecorded.v1, VitalsRecorded.v1
  API-->>UI: Case dashboard projection
  Physician->>UI: Review evidence and pending work
```

## ECG Upload to AI Result

```mermaid
sequenceDiagram
  actor Nurse
  participant UI as Streamlit UI
  participant API as FastAPI API
  participant ECG as ECG Intelligence
  participant Store as Evidence Storage
  participant AI as ECGAIProvider
  participant Outbox as Transactional Outbox
  Nurse->>UI: Upload/select ECG study
  UI->>API: POST /api/v1/cases/{id}/ecg-studies
  API->>Store: Store immutable evidence reference
  API->>ECG: UploadECG
  ECG->>Outbox: ECGUploaded.v1
  UI->>API: POST analysis request
  API->>ECG: RequestAIAnalysis
  ECG->>Outbox: AIAnalysisRequested.v1
  ECG->>AI: predict(normalized input contract)
  AI-->>ECG: NormalizedAIResult + model provenance
  ECG->>Outbox: AIAnalysisCompleted.v1
  Note over ECG,AI: No tensors/checkpoints leave adapter; no AI result triggers cath-lab action
  API-->>UI: Analysis read model and explicit limitations
```

## Troponin Result to Pathway Review

```mermaid
sequenceDiagram
  actor Nurse
  participant API as FastAPI API
  participant Trop as Troponin Intelligence
  participant Reason as Clinical Reasoning
  participant Alerts as Alerts
  participant Work as Workflow
  Nurse->>API: Record result with unit, collection/result time and source
  API->>Trop: RecordTroponinResult
  Trop->>Reason: TroponinResulted.v1 via outbox
  Reason->>Reason: Calculate declared delta; evaluate versioned demo rules
  Reason->>Alerts: Raise conflict review alert when evidence conflicts
  Reason->>Work: Request physician review task
  Reason-->>API: ClinicalPathwaySuggested.v1
  Note over Reason: Demonstration rule - not for clinical use; never AMI rule-out
```

## Cath-Lab Review Workflow

```mermaid
sequenceDiagram
  actor Physician
  participant UI as Streamlit UI
  participant API as FastAPI API
  participant Work as Workflow and Tasks
  participant Alert as Alerts
  participant Audit as Timeline/Audit
  Physician->>UI: Review case evidence and suggested pathway
  UI->>API: POST physician decision
  API->>Work: RecordPhysicianDecision
  Work->>Audit: PhysicianDecisionRecorded.v1
  alt physician requests cath-lab review
    Work->>Work: Verify physician confirmation exists
    Work->>Audit: CathLabReviewRequested.v1
    Work->>Audit: TaskCreated.v1
  else confirmation absent
    Work-->>API: ConsequentialActionRequiresPhysicianConfirmation
  end
  Alert->>Audit: Alert acknowledgement/resolution history
  Note over Work: This is a review request, never autonomous cath-lab activation
```

## Event Publication and Transactional Outbox

```mermaid
sequenceDiagram
  participant App as Application service
  participant DB as PostgreSQL transaction
  participant Outbox as Outbox dispatcher
  participant Handler as Idempotent handler
  App->>DB: Persist aggregate state change
  App->>DB: Persist event envelope in outbox
  App->>DB: Commit atomically
  Outbox->>DB: Claim undispatched event
  Outbox->>Handler: Deliver event_id
  alt successful
    Handler->>DB: Persist projection/task/alert + processed event ID
    Outbox->>DB: Mark dispatched
  else failure
    Handler-->>Outbox: Structured failure
    Outbox->>DB: Record attempt/error; schedule retry or dead-letter state
  end
```

