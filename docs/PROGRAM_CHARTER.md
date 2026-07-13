# VinAMI ACS Operating System - Program Charter

## Product

- **Product name:** VinAMI ACS Operating System
- **Vision:** Build a clinical workflow operating system for suspected Acute Coronary Syndrome (ACS).
- **Product principle:** AI is not the product. Clinical workflow is the product. ECG AI is one replaceable module.

## MVP Positioning and Safety Boundary

This repository will contain a research and engineering MVP. It is not:

- a clinically validated medical device;
- an AMI rule-out product;
- an autonomous cath-lab activation system;
- a replacement for physician judgment; or
- a production implementation of ESC or AHA guidelines.

Every demo clinical rule must visibly state: **"Demonstration rule - not for clinical use."**

The MVP enforces these non-negotiable rules:

1. ECG alone can never rule out AMI.
2. AI output can never directly activate a cath lab.
3. A physician confirmation is required for consequential clinical actions.
4. Conflicting ECG, troponin, and clinical information creates a review alert.
5. Every AI prediction records model name, version, timestamp, and input reference.
6. Every decision and workflow state transition is auditable.

## Repository Boundary

The existing `VinStroke-ECG` notebook, artifacts, reports, `src/` utilities, and current Streamlit application are an independent ECG Intelligence research prototype. They must be preserved unless a task explicitly changes that prototype.

`VinAMI ACS Operating System` will be developed as a separate modular-monolith application. It may consume the ECG prototype only through an adapter that implements the `ECGAIProvider` port. It must never import model-specific code into clinical domain or application logic.

## Architecture Strategy

The MVP uses a modular monolith. It applies:

- Domain-Driven Design;
- Hexagonal Architecture;
- Clean Architecture;
- dependency inversion;
- repository pattern and unit of work;
- event-driven domain interactions with a transactional outbox;
- CQRS only where it provides a clear read-model benefit; and
- explicit bounded contexts and dependency direction.

Microservices, Kubernetes, Kafka, and distributed infrastructure are out of scope unless an Architecture Decision Record (ADR) explicitly justifies the decision.

The backend is the system of record. A Streamlit UI may call only versioned FastAPI endpoints; it must contain no clinical business logic and make no direct database query.

## Bounded Contexts

1. Patient and Encounter
2. ACS Clinical Case
3. Triage
4. ECG Intelligence
5. Troponin Intelligence
6. Clinical Reasoning
7. Workflow and Tasks
8. Alerts and Escalation
9. Timeline and Audit
10. Model Registry and Learning Data
11. Identity and Access placeholder

Each context owns its domain language, application services, ports, and persistence mapping. Cross-context communication uses explicit commands, queries, and domain events rather than imports of internal domain models.

## AI Provider Boundary

Clinical and workflow modules consume normalized result contracts only. They must never import `torch`, `timm`, ONNX Runtime, tensors, or model-specific code.

The ECG Intelligence context exposes an `ECGAIProvider` port with:

- `predict()`;
- `explain()`;
- `health()`; and
- `get_model_info()`.

Planned adapters are:

- `MockECGAIProvider` for deterministic MVP workflows;
- an optional `TorchECGAIProvider` adapter around the preserved ConvNeXtV2 artifact; and
- a future ONNX adapter.

## Engineering Standards

New application code targets Python 3.12 and uses FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL, Alembic, pytest, Streamlit, structured logging, Ruff, mypy, pre-commit, and Docker Compose.

Required practices:

- complete typing and public-interface docstrings;
- no clinical business logic in routers or ORM models;
- no global mutable state;
- deterministic seed data;
- UTC timestamps and UUID identifiers;
- optimistic locking for workflow aggregates where appropriate;
- soft delete only with explicit justification;
- explicit transaction boundaries;
- idempotent commands and event handlers where appropriate; and
- structured errors and explicit failed-event handling.

## Sprint Completion Contract

At the end of every implementation sprint:

1. Run formatting, linting, type checking, and tests.
2. Update architecture documentation.
3. Add or update an ADR for significant decisions.
4. Print the exact commands used.
5. Provide a concise change summary and created/modified files.
6. State known limitations honestly.
7. Confirm Docker Compose still starts when the application stack exists.
8. Leave unrelated working modules unchanged.

