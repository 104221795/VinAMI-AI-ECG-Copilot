# VinAMI ACS Operating System

VinAMI ACS is a research and engineering MVP for suspected-ACS clinical workflow. It is not clinically validated, not an AMI rule-out product, not an autonomous cath-lab activation system, and not a replacement for physician judgment.

> **Demonstration rule - not for clinical use.** Sprint 5 adds a versioned state-machine workflow engine. It does not add a clinically validated pathway, a diagnosis, an AMI rule-out decision, API workflow commands, UI workflow, ECG model adapters, or autonomous actions.

Sprint 4 adds a PostgreSQL transactional outbox, internal dispatcher, idempotent projection handlers, retry/dead-letter state, and explicit replay. Sprint 5 uses that delivery mechanism for auditable workflow transitions, generated review tasks, alerts, and persisted due timers.

## Repository Boundary

This directory is a new modular-monolith application. The repository-root `app.py`, `src/`, notebook, `Research/`, and `VinStroke_ECG_artifacts/` remain an independent ECG research prototype. Future ACS ECG integration is only through the `ECGAIProvider` port; no model runtime belongs in clinical domain code.

## Architecture

- `apps/api`: FastAPI factory, `/health`, `/ready`, and `/metrics`.
- `apps/web`: Next.js clinical product frontend for the verified R1 lifecycle.
- `apps/dashboard`: Streamlit developer dashboard retained until the final F0 Docker gate permits its legacy transition.
- `apps/worker`: Redis-connected process that runs persisted due timers and the internal outbox dispatcher.
- `src/vinami/shared`: settings, structured logging, SQLAlchemy infrastructure, metrics, and composition root.
- `src/vinami/<context>/{domain,application,ports,adapters,api}`: package boundaries for each approved bounded context. They intentionally contain no clinical implementation in this sprint.
- `migrations`: Alembic runtime configuration for the research-MVP system of record.
- `tests`: unit, integration, architecture, and contract tests.

The dependency direction is delivery -> application -> domain. Infrastructure implements ports. Streamlit calls only `/api/v1` once clinical routes exist and must not query PostgreSQL or import domain services.

## Verified Frontend Slices

The Next.js product frontend exposes real PostgreSQL-backed data through FastAPI only:

`Command Center -> Patient/Encounter summary -> Case -> Timeline -> Immutable Audit`

R2 adds structured triage and vital documentation. R3 adds an ECG Workspace for artifact ingestion, technical quality, deterministic provider analysis, five independent label scores, serial evidence, and physician review. The R3 runtime is a research-use mock-provider demonstration, not real-model validation.

It uses controlled synthetic development identity. Production authentication was not exercised. See `docs/recovery/r3/r3-completion-report.md` for R3 gate status and limitations.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Endpoints:

- API health: `http://localhost:8000/health`
- API readiness: `http://localhost:8000/ready`
- API metrics: `http://localhost:8000/metrics`
- Next.js F0 UI: `http://localhost:3000`
- Streamlit developer dashboard: `http://localhost:8501` until the documented legacy transition
- Prometheus: `http://localhost:9090`

Fast frontend iteration after the API dependencies are running:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

## Commands

```bash
make install     # Local editable install with Python 3.12
make dev         # Docker Compose development stack
make test        # pytest inside the API image
make lint        # Ruff
make format      # Ruff formatter
make typecheck   # mypy --strict
make migrate     # Alembic upgrade head
make seed        # Validate platform seed prerequisites; creates no clinical records
make down        # Stop the Compose stack
```

Frontend quality commands:

```bash
pnpm quality
pnpm api:snapshot
pnpm api:generate
pnpm api:check
pnpm test:e2e
```

## Identity Modes

The API requires an explicit identity provider mode. Local Compose uses deterministic
synthetic identities:

```text
VINAMI_IDENTITY_MODE=development
X-Development-Identity: nurse
```

Only predefined fixture names are accepted; caller-supplied actor IDs and roles are not
authoritative. OIDC mode uses `Authorization: Bearer` and requires issuer, audience, JWKS
URL, allowed algorithms, and claim mappings shown in `.env.example`. Development identity
mode is prohibited for a production environment. See
`docs/recovery/r1-5/identity-architecture.md` for boundaries and limitations.

## Safety and Delivery Rules

- ECG alone can never rule out AMI.
- AI output can never directly activate a cath lab.
- Consequential actions require physician confirmation.
- Conflicting ECG, troponin, and clinical data must create a review alert when those contexts are implemented.
- Every future decision and state transition must be auditable through an outbox-backed event flow.
- The shipped workflow definition is explicitly labeled `Demonstration workflow — not for clinical use.` and carries no clinical thresholds.

Read the repository-level `docs/PROGRAM_CHARTER.md`, `docs/architecture/`, `docs/mvp/`, and `docs/adr/` before implementing a bounded context.
