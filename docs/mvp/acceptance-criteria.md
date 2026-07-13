# Acceptance Criteria

| ID | Criteria |
|---|---|
| AC-01 | A case cannot be opened without a valid encounter reference, actor, UTC time and command ID. |
| AC-02 | Every successful command has an audit entry and an outbox event in the same transaction. |
| AC-03 | A duplicate command/event ID does not create duplicate patient, task, alert, or projection side effects. |
| AC-04 | ECG analysis result always records provider, model name/version, processing timestamp and immutable input reference. |
| AC-05 | If provider analysis fails, the UI receives a clear structured error and the system records `AIAnalysisFailed.v1`; no failure is ignored. |
| AC-06 | ECG AI output cannot close a case, rule out AMI, activate a cath lab, or bypass physician confirmation. |
| AC-07 | A pathway output displays demonstration-rule wording, ruleset version, source facts, conflicts and review requirement. |
| AC-08 | Conflicting ECG, troponin and clinical facts create a review alert and physician-review task. |
| AC-09 | Cath-lab review/transfer request is rejected without a recorded physician confirmation. |
| AC-10 | Streamlit performs no direct database query and reaches the backend only through `/api/v1`. |
| AC-11 | Case timeline and audit history show ordered UTC events with actor and correlation IDs. |
| AC-12 | Existing VinStroke research notebook, artifacts, reports and UI remain unchanged by ACS tests/runs. |

