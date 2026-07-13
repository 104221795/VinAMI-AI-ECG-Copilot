# Data Classification

## Data Classes

| Class | Examples | MVP handling |
|---|---|---|
| Restricted clinical data | Patient reference, encounter location, symptoms, vitals, ECG/troponin evidence, physician decision | PostgreSQL/evidence storage only; API authorization boundary; audit every mutation; do not place in logs |
| Sensitive operational data | actor IDs, task assignment, alert state, audit events | least-privilege access; UTC audit trail; avoid public exports |
| Model and research metadata | model name/version, capability, input contract, aggregate metrics reference | model registry; distinguish from clinical facts |
| De-identified research artifacts | PTB-XL images, research reports, checkpoint metadata | preserve independently; no claim of local clinical validity |
| Public technical data | architecture docs, non-secret configuration templates | repository-safe after review; must not contain credentials or patient information |

## Data Rules

- Store only the minimum patient/encounter information required by the MVP workflow.
- Use UUIDs internally; never expose database sequence IDs as identifiers.
- Store timestamps in UTC and retain source/capture time separately where clinically relevant.
- ECG/troponin records must carry provenance and immutable evidence references; corrections append an auditable amendment rather than overwrite history.
- Structured logs include correlation IDs and error codes, never raw ECG content, symptoms, vitals, patient references, access tokens, or credentials.
- Exports are research case summaries, carry the demo/research disclaimer, and must be explicitly requested by an authorized actor.
- No learning-data reuse is allowed by default. Future use requires de-identification, governance, retention policy, and explicit ADR.

