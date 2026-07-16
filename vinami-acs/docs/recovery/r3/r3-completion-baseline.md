# R3 Completion Baseline

Recorded: 2026-07-14 (Asia/Saigon)

## Source and Runtime

- Branch: `frontend/f0-nextjs-clinical-slice`
- Commit: `e39f7539ac8e34d0bfc37c795fa6ee00a408d703`
- Working tree: existing uncommitted R3 documentation, frontend accessibility, and screenshot changes are preserved.
- PostgreSQL migration: `b7f3a9d1e6c2 (head)`.
- API: healthy and ready at the R3 schema revision.
- Next.js: healthy.
- Worker: running.
- Unexpected dead-letter outbox records: 0.
- Provider mode: deterministic mock provider. The external ConvNeXtV2 artifact is not mounted or exercised.

## Supported Sources Before Completion Work

| Source | Existing capability | Baseline limitation |
| --- | --- | --- |
| VinAMI canonical JSON | Upload, waveform normalization, quality, preview | Core path already verified |
| Local DICOM Part 10 waveform | `pydicom` parser and deterministic fixture | Narrow metadata, no focused API failure/retry evidence |
| Mock DICOM connector | One successful reference | No unavailable, timeout, malformed, or recoverable reference modes |
| Canonical XML `urn:vinami:ecg:canonical:1` | Secure parse, waveform, preview | No registry/profile provenance in workspace |
| PDF | Immutable upload and PDF preview | Document-only state not fully represented in UI/API capabilities |

## Existing Dynamic ECG

- Persists immutable comparison records.
- Rejects comparison when waveform, sampling rate, unit, lead configuration, or preprocessing differ.
- Computes deterministic per-lead similarity, normalized difference, amplitude ratio, and baseline shift.
- Computes score deltas only for identical model name/version.

Missing: partial/warning comparability, typed reasons required by the completion contract, explicit alignment and quality metrics, compatibility result metadata, comparison physician-review revisions, and professional comparison UI.

## Existing Repeat ECG

- Persists scheduled reminders.
- Supports acknowledge and completion with optimistic version checks.
- Emits outbox events.

Missing: due/overdue calculation, cancellation, completion-time ordering, immutable cancellation/completion timestamps, explicit origin safety, query-by-id, UI lifecycle, and final Timeline/Audit evidence.

## Exact Remaining Gaps

1. Persist the complete ingestion lifecycle, actor role, idempotency/correlation metadata, and retry lineage.
2. Add deterministic connector fault modes and controlled 503/504 mappings.
3. Expose case ingestion lists, retry, connector capabilities/health, and PDF document behavior.
4. Complete comparison contracts, score compatibility, physician comparison-review revisions, and serial ordering metadata.
5. Complete reminder due/overdue/cancel/linked-completion lifecycle and safety invariants.
6. Extend the existing ECG Workspace without changing the F0 shell.
7. Stabilize OpenAPI once, regenerate the TypeScript client once, run focused R3 completion E2E scenarios, then run the final non-destructive gate once.

No live PACS/DICOMweb endpoint, hospital credential, production identity, model training, real ConvNeXtV2 inference, or real Grad-CAM is part of this baseline.
