# Container View

## Containers

| Container | Responsibility | Technology target | Data access |
|---|---|---|---|
| ACS Streamlit UI | Case-oriented human interface; renders API responses and submits commands | Streamlit | Versioned FastAPI only |
| ACS API and application host | Commands, queries, domain policies, event dispatch, health checks | FastAPI, Python 3.12 | Application ports only |
| PostgreSQL | System-of-record tables, outbox, audit/timeline projections | PostgreSQL | Infrastructure repositories/unit of work only |
| Outbox dispatcher | Reliably dispatches committed domain events in-process in the MVP | Same deployable application | Transactional outbox repository |
| Evidence object store | References ECG files and exported research summaries | Local volume in dev; S3-compatible adapter later | Evidence storage port only |
| ECG provider adapter | Runs deterministic mock analysis or isolated Torch/ONNX integration | Infrastructure adapter | `ECGAIProvider` port only |

```mermaid
C4Container
title VinAMI ACS MVP - Container Diagram
Person(clinician, "Clinician", "Uses the workflow")
System_Boundary(vinami, "VinAMI ACS Operating System") {
  Container(ui, "ACS Streamlit UI", "Streamlit", "No business rules and no database access")
  Container(api, "ACS API and application host", "FastAPI / Python 3.12", "Versioned commands, queries, domain policies, ports, in-process dispatcher")
  ContainerDb(db, "ACS PostgreSQL", "PostgreSQL", "System of record, outbox, audit and read models")
  Container(worker, "Outbox dispatcher", "Python process", "Delivers committed events idempotently")
}
System_Ext(store, "Evidence object store", "Local/S3-compatible adapter")
System_Ext(ai, "ECG AI provider", "Mock now; Torch or ONNX later")
Rel(clinician, ui, "Uses", "HTTPS")
Rel(ui, api, "Calls /api/v1", "HTTPS/JSON")
Rel(api, db, "Reads/writes through repositories and UoW", "SQL")
Rel(worker, db, "Claims and marks outbox messages", "SQL")
Rel(api, store, "Stores evidence references", "Port")
Rel(api, ai, "Predicts/explains through ECGAIProvider", "Port")
Rel(api, worker, "Writes domain events to outbox in same transaction", "Database transaction")
```

## Runtime Constraints

- FastAPI is the sole system-of-record interface. UI calls `/api/v1` and does not import domain services or SQLAlchemy.
- The dispatcher is logically separate but may run in the same process or a second Compose process. It is not a distributed message broker.
- The optional Torch adapter may mount the preserved artifact read-only. It never writes to `VinStroke_ECG_artifacts`.
- PostgreSQL holds metadata and audit records; large ECG files and exports are addressed by immutable input/output references.

