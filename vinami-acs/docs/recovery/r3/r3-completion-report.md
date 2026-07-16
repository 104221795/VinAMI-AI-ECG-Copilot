# R3 Completion Report

Recorded: 2026-07-14 (Asia/Saigon).

## Gate Status

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| ECG Core | GO | Existing upload, quality, waveform, five-label deterministic analysis and physician review remain passing. |
| Hospital Ingestion Local/Mock | GO | Local DICOM, canonical XML, PDF document and deterministic mock DICOM connector were exercised. |
| Dynamic ECG | GO | Comparable and non-comparable serial studies, lead metrics, compatible score evolution and physician review persist. |
| Repeat ECG | GO | Schedule, acknowledge and completion with a subsequent ECG persist with optimistic versions. |
| R3 Research Product | GO | Backend, frontend, browser, migration and restart-persistence gates pass. |
| Real ConvNeXtV2 / Grad-CAM | DEFERRED | No real checkpoint inference or real Grad-CAM was exercised. |
| Live hospital connection | DEFERRED | No live PACS, DICOMweb endpoint or hospital credential was available. |

GO applies only to the local research product. It is not clinical validation, production readiness or permission to use VinAMI for patient-care decisions.

## Delivered

- Persisted ECG ingestion jobs with safe provenance, failure state, correlation ID, retry count and optimistic version.
- Local DICOM Part 10 waveform ingestion through `pydicom`, plus deterministic mock connector success, timeout, unavailable, missing and malformed modes.
- Secure namespace-aware canonical XML profile `urn:vinami:ecg:canonical:1`; no claim of broad vendor compatibility.
- PDF upload, immutable artifact and in-browser preview as document-only evidence. PDF never creates waveform samples and cannot enter waveform AI analysis.
- Dynamic ECG comparability assessment, neutral reasons, deterministic per-lead metrics, compatible model-score deltas and append-only physician comparison review.
- Repeat reminder schedule, due/overdue representation, acknowledge, complete and cancel transitions. An AI score is not an allowed reminder origin.
- Versioned FastAPI contracts, regenerated OpenAPI/TypeScript client and API-only Next.js route `/cases/[caseId]/ecg`.
- Transactional outbox, Timeline and immutable Audit projection for the new actions.

## Safety Position

The deterministic mock provider remains configured. No model training occurred. Scores are independent research model scores, not clinical probabilities. The UI uses “MI-related ECG pattern,” not AMI diagnosis. ECG cannot rule out AMI, AI cannot activate a cath lab, and technical change cannot be interpreted as disease progression. Physician review remains required.

Production authentication was not exercised. The development identity mode is controlled and visibly labeled. The system is not clinically validated, not production-ready and must not be used for patient-care decisions.

## Runtime Evidence

The final non-destructive API/worker restart retained 44 ingestion jobs, 8 comparisons, 5 Dynamic ECG physician reviews and 3 repeat reminders. The outbox contained 705 published events and zero dead-letter rows. PostgreSQL remained at `c8a4e7f2d913 (head)` and `alembic check` found no drift.

## R4 Recommendation

GO to begin R4 Troponin Intelligence as a separate bounded-context vertical slice. Do not widen ECG claims or introduce pathway automation while doing so.
