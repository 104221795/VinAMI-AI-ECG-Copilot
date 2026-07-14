# R2.1 Test Report

Recorded 2026-07-14.

## Quality Gate

| Gate | Result |
| --- | --- |
| Ruff format | PASS: 206 Python files |
| Ruff lint | PASS |
| Full-repository mypy | PASS: 173 source files |
| Full backend pytest | PASS: 93 tests; 2 dependency deprecation warnings |
| Alembic current | PASS: `a2c4e6f8b0d1 (head)` |
| Alembic check | PASS: no new upgrade operations |
| Frontend format | PASS |
| ESLint | PASS |
| TypeScript | PASS across contracts, UI, API client, and web |
| OpenAPI drift | PASS: `08bface127096fcb088b677b1de76b1fd9c2521e076112ce0096b95b5eeeeefe` |
| Vitest | PASS: 9 files, 33 tests |
| Next.js production build | PASS; case route first-load JS 152 kB |
| Full Playwright | PASS: 36 passed, 14 skipped by policy/storybook absence |
| R2 Playwright journeys | PASS: 17 passed, 5 skipped by viewport policy |
| axe WCAG checks | PASS on covered R1/R2 workspaces and failure states |
| Visual regression | PASS after updating the case-workspace snapshot for the R2 documentation section |

## Mypy Root Cause and Correction

Root cause: the legacy Streamlit dashboard was both an `apps.dashboard` package and an extra mypy source root through `mypy_path = ["apps/dashboard"]`. That made files resolvable through ambiguous module paths and encouraged local imports such as `api.client` and `models.view_models`.

Correction:

- Removed `mypy_path` from `pyproject.toml`.
- Converted legacy Streamlit imports to package-absolute imports under `apps.dashboard.*`.
- Kept Streamlit in the primary mypy gate as checked legacy code; it is still not the default product frontend.

Current mypy configuration checks `src`, `apps/api`, `apps/worker`, selected `apps/dashboard` entry/support files, and `scripts`, with `strict = true`.

## Playwright Coverage Added

R2.1 adds end-to-end coverage for:

- Scenario A: record triage through the UI, reload, verify revision, Timeline, Audit, actor and correlation context.
- Scenario B: record repeated vitals through the UI, reload, verify history ordering, Timeline and Audit.
- Scenario C: correct triage with required correction reason and append-only revision history.
- Scenario D: correct vitals with required correction reason and append-only revision history.
- Scenario E: stale concurrency conflict with HTTP 409, visible stale-data guidance, preserved draft, and no silent overwrite.
- Scenario F: duplicate submission through persistent idempotency with exactly one effective triage record.
- Scenario G: validation and permission behavior for empty vitals, unsafe unit rejection, read-only write denial, and controlled errors.

Desktop runs all write/correction/concurrency/idempotency/validation journeys. Tablet runs the primary record-triage and record-vitals flows plus persisted workspace and BFF boundary coverage.

## Runtime Verification

- API readiness: `ready`, schema revision `a2c4e6f8b0d1`, identity mode `development`.
- Web health: `healthy`.
- API container: healthy.
- Worker container: running.
- PostgreSQL after non-destructive restarts: 46 triage revisions, 41 vital-set revisions, 0 dead-letter outbox events.

## Warnings

- Starlette warns that the current TestClient/httpx integration will migrate to `httpx2`.
- FastAPI deprecates the old constant name `HTTP_422_UNPROCESSABLE_ENTITY`.
- Next.js build warns that the Next ESLint plugin is not detected in the current ESLint configuration; the lint command still passes.
