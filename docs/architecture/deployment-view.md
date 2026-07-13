# Deployment View

```mermaid
flowchart TB
  clinician["Clinician browser"] --> ui["acs-ui container\nStreamlit"]
  ui --> api["acs-api container\nFastAPI /api/v1"]
  api --> db[("postgres container\nwrite model, outbox, audit, projections")]
  api --> storage["dev evidence volume\nfuture S3 adapter"]
  dispatcher["acs-dispatcher container\nor API background process"] --> db
  api --> provider["MockECGAIProvider\noptional read-only Torch adapter"]
  provider -. read-only .-> artifacts["Preserved VinStroke ECG artifacts\nnot part of ACS database"]
```

## Docker Compose MVP

- Sprint 2 introduces `vinami-acs/docker-compose.yml` with `postgres`, `redis`, `api`, `dashboard`, `worker`, and `prometheus` services. The API image is Python 3.12; dashboard and worker reuse the same image.
- `postgres` is the only database. Local volumes are used only for development data and evidence references.
- API liveness is exposed at `/health`, readiness probes PostgreSQL at `/ready`, and `/metrics` exposes Prometheus metrics. API health checks gate dashboard and Prometheus startup. Secrets are injected by environment variables and are never committed.
- The preserved ECG artifacts are optional, read-only mounts. The MVP must work with `MockECGAIProvider` and no GPU.
- Production deployment topology, backup/restore, IAM, encryption keys, telemetry retention, and high availability remain unresolved and are out of Sprint 0 scope.
