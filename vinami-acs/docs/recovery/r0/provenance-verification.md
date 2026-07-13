# Provenance Verification

## ECG

The domain and ORM now preserve source system, source record ID, acquisition and ingestion timestamps, vendor/device, input format, sampling rate, lead configuration, quality status, model input reference, model name/version, provider name, and inference completion timestamp.

## Troponin

The domain and ORM now preserve source system, source record ID, assay manufacturer/name, analyzer, raw value, unit, reference limit and metadata, collection/result/ingestion timestamps, and quality flags. Repository mapping no longer fabricates current timestamps during rehydration.

## Verification

`test_ecg_and_troponin_provenance_round_trip` writes and reloads both aggregates through the production SQLAlchemy unit of work against PostgreSQL and asserts the complete provenance contract. Unsupported required fields are validated rather than silently discarded.

R0 does not assert medical-device interoperability conformance; format vocabularies and external source identity governance remain R1+ concerns.
