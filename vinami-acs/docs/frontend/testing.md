# Frontend Testing

## R3 Additions

R3 adds component tests for 12-lead waveform rendering, independent multi-label ranking, safety language, and the empty state. The Playwright golden path creates real lifecycle records, uploads deterministic synthetic ECG data, runs the provider, records physician review, checks axe accessibility, and captures desktop/tablet waveform and ranking evidence under `docs/frontend/screenshots/`.

## R2 Additions

R2 adds component coverage for explicit uncertainty, neutral empty/completeness states, and append-only correction forms; API-client coverage for typed command bodies and stable idempotency headers; and Playwright coverage for persisted complete/corrected cases, BFF allow-list behavior, axe checks, and desktop/tablet overflow. Baselines are `r2-case-workspace-desktop.png` and `r2-case-workspace-tablet.png`.

## Layers

- Vitest: 35 unit, component, integration and architecture tests across 10 files in the R3 run.
- Storybook production build: reusable primitives and operational states.
- Playwright lifecycle: real PostgreSQL-backed R1 queue, case, Timeline and Audit at desktop and tablet widths.
- Playwright failures: controlled identity, transport, contract, offline and projection states.
- axe-core: major pages and Storybook operational states.
- Visual regression: case-workspace pixel baseline plus documentation screenshots at 1920, 1440, 1280 and tablet widths.

Playwright uses one worker because projects share deterministic seed data and write named visual baselines. This prevents cross-project navigation and screenshot races while still executing both viewports.

Primary commands:

```bash
pnpm quality
pnpm test:e2e
STORYBOOK_BASE_URL=http://127.0.0.1:6006 pnpm test:e2e
```

The browser suites require the R1 API and seeded PostgreSQL projections. State visuals require the built Storybook to be served.
