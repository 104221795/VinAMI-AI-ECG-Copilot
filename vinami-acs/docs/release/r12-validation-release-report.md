# R12 Validation and Release Hardening Report

Date: 2026-07-16

Scope: VinAMI ACS Operating System research-use prototype. This report does not claim clinical validation, regulatory approval, hospital production readiness, or suitability for autonomous patient-care decisions.

## Release Gate Decision

| Gate                    | Decision                   | Evidence                                                                                                                                                       |
| ----------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Functional/Product Gate | PASS                       | Backend tests, frontend quality gate, R7/R8/R10 browser evidence passed.                                                                                       |
| Data/Safety Gate        | PASS WITH PROTOTYPE LIMITS | Backend domain/API suites passed; migration head and drift checks passed; safety wording and authority boundaries remain represented in tests.                 |
| Browser Evidence Gate   | PARTIAL PASS               | Mandatory R10 browser evidence passed; R7/R8 critical desktop suites passed. Full desktop Playwright suite timed out at 10 minutes and is not claimed passing. |
| Release Gate            | CONDITIONAL GO             | Suitable as a Research Prototype Release Candidate after acknowledging security-scan and full-browser-suite evidence gaps.                                     |

## Defects Fixed During R12

1. SSE streams could remain visually stuck in `connecting` when no event had been emitted for a new case. Fixed by sending an initial SSE heartbeat comment before polling events.
2. Real-time integration events refreshed the case workspace but did not refresh the integration ledger panel. Fixed by invalidating the `r10-integration-status` query from Command Center and Case Workspace real-time handlers.
3. Command Center selected-case workspace links could be swallowed by re-render/refresh timing. Hardened links with an explicit mouse navigation fallback while preserving semantic `href` links.
4. Added the deferred R10 Playwright/axe evidence suite:
   - `R10 Scenario A - real-time lab import refreshes authoritative case data without duplicates`
   - `R10 Scenario B - reconnect state and failed integration message remain visible`

## Commands Executed

```bash
docker compose up --build -d api web
docker compose up --build -d web
docker compose restart api worker web
docker compose ps
docker compose exec -T api python -m ruff format --check .
docker compose exec -T api python -m ruff check .
docker compose exec -T api python -m mypy src apps scripts
docker compose exec -T api python -m pytest -q
docker compose exec -T api alembic current
docker compose exec -T api alembic check
pnpm.cmd quality
pnpm.cmd exec playwright test apps/web/e2e/r10-realtime-integration.spec.ts --project=desktop
pnpm.cmd exec playwright test apps/web/e2e/r7-command-center.spec.ts --project=desktop
pnpm.cmd exec playwright test apps/web/e2e/r8-complete-case-workspace.spec.ts --project=desktop
pnpm.cmd exec playwright test --project=desktop
pnpm.cmd audit --audit-level high --prod
```

Health and smoke checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-WebRequest http://127.0.0.1:3000/api/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:3000/command-center -UseBasicParsing
```

## Passed Checks

### Backend

| Check             | Result                                                     |
| ----------------- | ---------------------------------------------------------- |
| Ruff format check | PASS, 471 files already formatted                          |
| Ruff lint         | PASS                                                       |
| mypy              | PASS, no issues in 232 source files                        |
| Full pytest       | PASS, 135 passed                                           |
| Alembic current   | PASS, `f3b6c8d1e245 (head)`                                |
| Alembic check     | PASS, no new upgrade operations detected                   |
| API readiness     | PASS, `/ready` returned `ready` at revision `f3b6c8d1e245` |

Warnings:

- Starlette/httpx TestClient deprecation warning.
- Pydantic warning for development identity header metadata.

### Frontend

| Check                      | Result                                                                        |
| -------------------------- | ----------------------------------------------------------------------------- |
| Prettier format check      | PASS                                                                          |
| ESLint                     | PASS                                                                          |
| TypeScript typecheck       | PASS                                                                          |
| OpenAPI drift check        | PASS, hash `53af894f1b6373303c03d3c8f1a89eb2b50971f8dca38ff046365cc79107c2d8` |
| Vitest                     | PASS, 41 tests in 14 files                                                    |
| Storybook production build | PASS                                                                          |
| Next.js production build   | PASS during Docker web rebuild                                                |

Non-blocking frontend warnings:

- Storybook/Vite CJS API deprecation.
- Bundler warnings for `"use client"` directives in dependencies.
- Large Storybook chunks.

### Browser Evidence

| Suite                                            | Result                                                   |
| ------------------------------------------------ | -------------------------------------------------------- |
| R10 real-time and integration Playwright desktop | PASS, 2 passed                                           |
| R7 Command Center Playwright desktop             | PASS, 2 passed                                           |
| R8 Complete Case Workspace Playwright desktop    | PASS, 2 passed                                           |
| Full desktop Playwright suite                    | NOT PASSED AS A GATE: command timed out after 10 minutes |

R10 axe coverage:

- Real-time connection status.
- Real-time notification state.
- Integration failed-message view.

### Runtime and Recovery

| Check                                          | Result                                         |
| ---------------------------------------------- | ---------------------------------------------- |
| Non-destructive restart of API, worker and web | PASS                                           |
| API ready after restart                        | PASS                                           |
| Web health after restart                       | PASS                                           |
| Command Center route after restart             | PASS                                           |
| Docker service status                          | API/web/postgres/redis healthy; worker running |

## Performance Smoke

Small local prototype smoke test, 20 sequential requests per endpoint:

| Endpoint group             | Count | Min ms | P50 ms | P95 ms | Max ms |
| -------------------------- | ----: | -----: | -----: | -----: | -----: |
| Command Center queue       |    20 |     43 |     49 |    189 |    325 |
| Case Workspace read model  |    20 |     22 |     24 |     30 |     31 |
| Integration message ledger |    20 |      9 |     11 |     13 |     22 |

These are local prototype measurements only, not hospital-scale capacity evidence.

## Security Findings and Gaps

Executed attempts:

- `python -m bandit --version`: failed because `bandit` is not installed in the API image.
- `python -m pip_audit --version`: failed because `pip-audit` is not installed in the API image.
- `pnpm audit --audit-level high --prod`: failed because the npm audit endpoint returned HTTP 410 from the registry.

Security gate status: evidence gap. No critical vulnerability was found by the executed tests, but automated dependency/static security scanning is incomplete.

Recommended hardening before any stronger release claim:

1. Add `bandit` and `pip-audit` to a security CI job or separate tooling image.
2. Replace `pnpm audit` with a currently supported advisory source or GitHub Dependabot/SCA.
3. Add security-header and rate-limit assertions to API/browser tests.
4. Add log redaction tests for patient-like identifiers.

## Evidence-Only Gaps

- Full Playwright desktop suite timed out; only R7/R8/R10 critical suites are claimed passing.
- No tablet/mobile R10 Playwright run was executed in this R12 pass.
- No k6/Locust sustained load test was added.
- No OWASP ZAP, Trivy, Bandit or pip-audit scan completed.
- No destructive recovery test was run, by design.
- Follow-up Scheduling was not independently audited beyond existing history fields and available tests.

## Final Recommendation

CONDITIONAL GO for a Research Prototype Release Candidate.

Conditions:

1. Treat this as a research and engineering prototype only.
2. Do not present the system as clinically validated or production hospital ready.
3. Complete the security scan toolchain and full-browser-suite stabilization before any public release or formal demo gate.
4. Keep the safety language visible: AI and simulated integrations do not create diagnosis, cath-lab authority, discharge authority or physician decisions.
