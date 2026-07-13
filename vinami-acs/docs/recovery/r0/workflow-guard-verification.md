# Workflow Guard Verification

## Authority boundary

| Input | Generic fact patch | Can authorize cath-lab review |
|---|---:|---:|
| ECG available or AI score | Yes, as observation | No |
| Troponin available | Yes, as observation | No |
| Persisted physician decision ID | No | Yes, after all guards pass |
| Boolean `physician_decision_recorded` | Rejected | No |

The application handler loads the decision and actor from repositories. The aggregate then verifies:

- decision type is `CATH_LAB_REVIEW_REQUESTED`;
- status is effective and no later revocation exists;
- case ID, actor ID, actor role, workflow version, and case expected version match;
- command correlation context is present;
- optimistic workflow version is current.

## Regression coverage

`tests/unit/test_workflow_engine.py` covers generic-patch bypass, actorless commands, missing decisions, wrong type, revoked record, AI-only facts, duplicate commands, and stale workflow versions. `tests/integration/test_r0_recovery.py` proves persisted physician authority, non-physician rejection, and append-only revocation behavior against PostgreSQL.

The transition emits `CathLabReviewRequested`; it does not represent cath-lab activation and cannot be emitted directly by an AI provider.
