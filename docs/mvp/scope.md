# MVP Scope

## In Scope

- Manually register a local patient reference and encounter.
- Open, review, and close a suspected-ACS case with auditable state changes.
- Record symptoms, vitals, ECG study metadata, ECG quality state, troponin order/collection/result facts, and transparent delta calculations.
- Run deterministic mock ECG analysis; optionally use a read-only adapter to the independent VinStroke-ECG artifact.
- Show normalized AI outputs, provenance, explanation references and limitations.
- Evaluate versioned transparent demonstration rules, create review alerts/tasks, require physician confirmation, and maintain timeline/audit history.
- Expose versioned FastAPI APIs and an API-only Streamlit workflow UI.
- Export a research case summary with disclaimers.

## Explicitly Out of Scope

- Clinical validation, diagnosis, AMI rule-out, risk scoring, autonomous cath-lab activation, real ESC/AHA guideline implementation, order entry, medication advice, billing, and production EHR/LIS/identity integration.
- Real-time device ingestion, background GPU inference, training/retraining, learning-data reuse, multi-site deployment, and patient-facing use.
- Rewriting or embedding the existing VinStroke-ECG research notebook/UI/artifacts.

