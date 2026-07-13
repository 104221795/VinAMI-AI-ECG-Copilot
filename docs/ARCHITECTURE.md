# VinAMI ACS Architecture Baseline

## Current Repository Assessment

The repository currently contains a self-contained `VinStroke-ECG` research prototype:

- a Kaggle notebook with PTB-XL preprocessing, CWT/STFT rendering, ConvNeXt training, evaluation, calibration, Grad-CAM, and export;
- local artifacts containing a ConvNeXtV2 checkpoint, reports, image representations, manifests, and model metrics; and
- a Streamlit research workspace that reads those artifacts directly.

The independent prototype remains unchanged while `vinami-acs/` is built alongside it. Sprint 2 added the technical platform scaffold. Sprint 3 adds a framework-free domain model, PostgreSQL persistence adapters, transactional outbox staging, and an Alembic system-of-record migration; it still has no clinical API or UI workflow.

## Target Modular Monolith

```text
VinAMI ACS
  API / FastAPI routers
      -> application commands and queries
          -> domain aggregates, policies, events, ports
              -> infrastructure adapters
                  -> PostgreSQL, outbox dispatcher, ECG providers

Streamlit ACS UI
  -> /api/v1 FastAPI only

VinStroke-ECG research prototype
  -> optional TorchECGAIProvider adapter
```

Dependency direction is inward. Infrastructure and delivery layers depend on application/domain contracts; the domain has no dependency on FastAPI, SQLAlchemy, Streamlit, torch, timm, or ONNX Runtime.

## Context Ownership

| Context | Owns | Primary integration |
|---|---|---|
| Patient and Encounter | patient identity reference, encounter metadata | case creation |
| ACS Clinical Case | case lifecycle and version | workflow and audit events |
| Triage | acuity intake data and triage assessment | case review |
| ECG Intelligence | ECG input reference and normalized AI result | clinical reasoning events |
| Troponin Intelligence | measurements, provenance, trend interpretation | clinical reasoning events |
| Clinical Reasoning | review-required outcomes and safety constraints | tasks and alerts |
| Workflow and Tasks | assigned review tasks and confirmations | audit events |
| Alerts and Escalation | safety/review alerts and acknowledgements | timeline events |
| Timeline and Audit | immutable user/system events | query read models |
| Model Registry and Learning Data | model metadata and prediction provenance | ECG Intelligence |
| Identity and Access | actor placeholder and roles | command authorization boundary |

## Safety-by-Design Flow

1. A clinician creates an ACS case for an encounter.
2. ECG and troponin evidence are recorded with provenance.
3. ECG Intelligence calls an `ECGAIProvider` and records normalized output plus model provenance.
4. Clinical Reasoning applies only declared demonstration rules and can create a review alert for conflicting evidence.
5. Workflow creates a clinician-review task. Consequential actions require a documented physician confirmation.
6. Every command, transition, AI prediction, and alert is written to the audit timeline through the transactional outbox.

No step produces an AMI rule-out, autonomous cath-lab activation, or a clinical guideline recommendation.

## Initial Delivery Sequence

1. Establish the application skeleton, PostgreSQL connectivity, Alembic runtime configuration, test tooling, and Docker Compose. Completed in Sprint 2.
2. Implement aggregate behavior, persistence adapters, migration, optimistic concurrency, and transactional-outbox staging. Completed in Sprint 3.
3. Implement the versioned internal outbox dispatcher, idempotent consumer ledger, retry/dead-letter handling, replay CLI, and projection-only handlers. Completed in Sprint 4; no application services or delivery endpoints were added.
4. Implement deterministic mock ECG and troponin providers with normalized contracts.
5. Implement safety policies, review alerts, and physician-confirmed workflow tasks through application commands.
6. Add API-only Streamlit case review UI.
7. Add the optional Torch adapter without changing the ECG prototype.
