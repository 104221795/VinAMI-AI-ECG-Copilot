# R3 Hospital ECG Ingestion

## Supported Scope

- Local DICOM Part 10 waveform through maintained `pydicom` parsing.
- Deterministic mock DICOM source `mock-dicom-source`; no live PACS or DICOMweb.
- VinAMI canonical XML profile `urn:vinami:ecg:canonical:1`, version 1.0.0.
- PDF as an immutable, previewable clinical document only.

XML parsing rejects DTD/entity content, disables network resolution, checks namespace/profile, limits content size and never claims support for every ECG vendor. DICOM extraction preserves technical UID metadata away from the primary clinical view and does not invent missing leads or units.

## Failure and Retry

The mock connector deterministically supports success, unavailable, not-found, timeout, malformed and retry-success behavior. Failure category and a controlled detail remain persisted. Retry uses expected version and idempotency key, increments retry count and does not create a duplicate job or completed study.

PDF never creates waveform samples, never enters Dynamic ECG waveform comparison and never enters the waveform model path. A physician can still record a document review.
