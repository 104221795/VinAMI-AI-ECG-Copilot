# Traceability Matrix

| Requirement / safety rule | Design source | Primary use cases | Events / tests to implement in Sprint 1+ |
|---|---|---|---|
| ECG alone never rules out AMI | Charter, ADR-006 | UC-05, UC-06, UC-09 | `AIAnalysisCompleted.v1`; policy unit tests |
| AI never activates cath lab | Charter, ADR-004/006 | UC-05, UC-10, UC-11 | `CathLabReviewRequested.v1`; forbidden-transition tests |
| Physician confirmation is required | Charter, ADR-006 | UC-10, UC-11 | `PhysicianDecisionRecorded.v1`; authorization/precondition tests |
| Conflict creates review alert | Charter, bounded contexts | UC-09, UC-12 | `AlertRaised.v1`, `PhysicianReviewRequested.v1`; ruleset tests |
| AI provenance is recorded | Charter, ADR-004 | UC-05, UC-06, UC-14 | `AIAnalysisCompleted.v1`; provider contract tests |
| State transitions are auditable | Charter, ADR-003 | UC-01 through UC-15 | all events; UoW/outbox integration tests |
| UI has no direct DB/rules | Charter, ADR-005 | UC-01 through UC-15 | dependency/import test; API client tests |
| Troponin delta is transparent | bounded contexts, scope | UC-07, UC-08, UC-09 | `TroponinResulted.v1`; calculation/version tests |
| Existing ECG prototype is preserved | Charter, ADR-001/004 | UC-05, UC-06 | artifact read-only/inventory check |
| Demo-rule wording is visible | Charter, ADR-006 | UC-09, UC-15 | API/UI contract tests |

