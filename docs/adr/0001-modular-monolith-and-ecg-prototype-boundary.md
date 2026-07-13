# ADR 0001: Adopt a modular monolith and preserve the ECG prototype boundary

- **Status:** Superseded by `ADR-001-modular-monolith.md`
- **Date:** 2026-07-13
- **Decision owners:** VinAMI ACS Operating System architecture

## Context

This repository contains a working VinStroke-ECG research prototype with a Kaggle notebook, a trained ConvNeXtV2 artifact, research reports, and a direct Streamlit artifact viewer. The new product is an ACS clinical workflow operating system, not an ECG-model product.

Clinical workflow must remain testable and safe when its ECG model is changed, unavailable, or replaced. The repository has no existing backend service, database, migration system, or distributed-system requirement.

## Decision

Build VinAMI ACS as a modular monolith with explicit bounded contexts and hexagonal dependencies. The backend will be the system of record. A future Streamlit ACS UI will use only versioned FastAPI endpoints.

Keep all existing VinStroke-ECG research code, notebook, reports, artifacts, and research Streamlit workspace independent. The ACS code may access an ECG model only through the `ECGAIProvider` port. The first provider is deterministic mock behavior; a Torch adapter is optional and remains isolated in infrastructure.

Clinical business logic may consume only normalized AI result contracts. It may not import torch, timm, ONNX Runtime, checkpoint formats, or tensors.

## Consequences

### Positive

- Clinical workflow can be developed and tested without a GPU or an ML runtime.
- ECG models can be replaced without changing clinical policies or workflows.
- The current research prototype remains reproducible and undisturbed.
- A single deployable unit keeps the MVP operationally simple while preserving strong boundaries.

### Trade-offs

- Explicit ports, event contracts, repositories, and a unit of work add upfront structure.
- The current direct Streamlit ECG viewer is not the future ACS UI and must not gain ACS clinical logic.
- Cross-context events are in-process initially; the transactional outbox preserves a reliable path to asynchronous delivery later.

## Rejected Alternatives

- **Embed ConvNeXtV2 directly in ACS case logic:** rejected because it couples clinical workflow to a research artifact and model runtime.
- **Rewrite the current VinStroke Streamlit app into the ACS product:** rejected because it would mix research presentation, database access, and clinical workflow concerns.
- **Start with microservices/Kafka/Kubernetes:** rejected because the MVP has no demonstrated distributed-systems need.
