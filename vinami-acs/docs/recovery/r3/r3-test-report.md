# R3 Test Report

Recorded: 2026-07-14.

## Final Quality Gate

| Check | Result |
| --- | --- |
| Ruff format | PASS: 221 files |
| Ruff lint | PASS |
| mypy | PASS: 194 source files |
| Focused R3 completion backend | PASS: 6 tests |
| Full backend pytest | PASS: 108 tests, 2 deprecation warnings |
| Prettier | PASS |
| ESLint | PASS |
| TypeScript | PASS: all workspaces |
| OpenAPI drift | PASS: `c8a125d...bd1e2` |
| Vitest | PASS: 10 files, 35 tests |
| Next.js production build | PASS, including `/cases/[caseId]/ecg` |
| R3 core Playwright desktop | PASS |
| R3 completion Playwright | PASS: 6 passed, 2 intentional tablet skips |
| axe-core | PASS in scenarios A-D |
| Alembic current/check | PASS: `c8a4e7f2d913`, no drift |
| Runtime restart persistence | PASS |
| Unexpected dead letters | PASS: zero |

The two Playwright skips are the required matrix: failure/retry and repeat/concurrency run on desktop only; hospital ingestion and Dynamic ECG run on desktop and tablet.

## Browser Scenarios

1. DICOM connector, canonical XML and PDF-only ingestion with provenance and preview.
2. Persisted connector timeout followed by safe retry without duplicate job.
3. Comparable serial ECGs, synchronized side-by-side waveforms, lead metrics, compatible score evolution and physician review.
4. Repeat reminder schedule, acknowledge, subsequent-study completion and optimistic version behavior.

The API integration suite additionally covers PDF waveform rejection, persisted retry state, score-evolution compatibility, outbox projection and reminder completion linkage. Existing R3 tests cover unsafe XML, authorization, malformed artifacts, idempotency and stale write protection.

## Defects Found and Fixed

- Source/Integration was initially hidden on an empty case because capability keys were interpreted too narrowly.
- Failed connector imports did not refresh the persisted job before presenting the controlled timeout.
- Current-study analysis selection could accidentally show a prior study analysis.
- PDF document review was incorrectly coupled to the presence of an AI analysis.
- The frontend architecture guard still prohibited the now-approved ECG route.
- Browser locators were made specific where multiple valid safety messages shared wording.

## Visual Evidence

Ten captures were generated: eight desktop states plus DICOM and Dynamic ECG tablet states under `docs/frontend/screenshots/r3-completion-*.png`. Full-page captures show browser sticky-shell behavior; the interactive viewport remained responsive and axe-clean.

## Warnings

Backend tests report only Starlette/httpx and HTTP 422 naming deprecations. The Next.js build reports that its optional ESLint plugin is not configured; repository ESLint itself passes.
