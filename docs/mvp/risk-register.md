# Risk Register

| ID | Risk | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|
| R-01 | MVP is mistaken for clinical decision support approval | Unsafe use | Persistent research/demo labels, safety gates, no diagnostic claims | Product/Clinical governance | Open |
| R-02 | ECG prototype is over-interpreted as ACS/AMI model | Incorrect workflow action | Adapter boundary, normalized limitations, no ECG-only rule-out | Architecture | Open |
| R-03 | Demo rules copied or presented as guidelines | Clinical misinformation | Ruleset versioning, visible disclaimer, clinical review before any expansion | Clinical governance | Open |
| R-04 | Model provider fails or is slow | Incomplete review | Mock default, health status, failed-analysis event, clear retryable error | Engineering | Open |
| R-05 | Event handler duplicates work | Duplicate tasks/alerts | Outbox event IDs and idempotency records | Engineering | Open |
| R-06 | Event handler failure is hidden | Missing audit/alert state | Structured failure storage, retry/dead-letter state and operations view | Engineering | Open |
| R-07 | UI bypasses backend rules | Divergent behavior | API-only UI ADR, import/dependency checks and API tests | Engineering | Open |
| R-08 | Sensitive data appears in logs/exports | Privacy breach | Structured logging policy, redaction tests, explicit export controls | Security | Open |
| R-09 | External EHR/LIS semantics differ | Incorrect data mapping | Adapter contracts, source provenance, integration-specific ADR | Integration | Open |
| R-10 | Optimistic-lock conflict overwrites workflow change | Lost update | Expected-version commands and conflict response | Engineering | Open |
| R-11 | Research artifacts are altered by ACS work | Loss of reproducibility | Read-only artifact mount; checksum/inventory checks; separate modules | Research/Engineering | Open |
| R-12 | Identity placeholder is treated as production access control | Unauthorized access | Explicit placeholder labeling; block production deployment | Security | Open |

