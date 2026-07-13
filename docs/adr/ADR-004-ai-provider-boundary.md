# ADR-004: Isolate ECG AI Behind a Provider Port

- **Status:** Accepted
- **Date:** 2026-07-13

## Decision

The ECG Intelligence context defines `ECGAIProvider` with `predict()`, `explain()`, `health()`, and `get_model_info()`. Workflow and reasoning use a normalized result contract. `MockECGAIProvider` is the MVP default; optional Torch and future ONNX providers are infrastructure adapters.

## Rationale

The preserved VinStroke-ECG ConvNeXtV2 artifact is research work, not an ACS workflow dependency. Its output must not leak implementation details or gain authority over clinical actions.

## Consequences

- No `torch`, `timm`, ONNX Runtime, checkpoint, or tensor import exists in business logic.
- Each result stores model name, version, timestamp, input reference, provider status, outputs and limitations.
- AI completion can request human review through facts/events; it cannot rule out AMI or activate a cath lab.

