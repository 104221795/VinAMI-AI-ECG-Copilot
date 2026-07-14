# R2 Visual Baseline Inventory

Recorded 2026-07-14.

Baselines are stored under `docs/frontend/screenshots/`. They are candidate review baselines generated from the running Next.js UI and FastAPI backend, with animations disabled by Playwright during capture.

| State | Desktop | Tablet |
| --- | --- | --- |
| Empty triage state | `r2-empty-triage-state-desktop.png` | `r2-empty-triage-state-tablet.png` |
| Completed triage summary | `r2-completed-triage-summary-desktop.png` | `r2-completed-triage-summary-tablet.png` |
| Incomplete documentation summary | `r2-incomplete-documentation-summary-desktop.png` | `r2-incomplete-documentation-summary-tablet.png` |
| Triage entry form | `r2-triage-entry-form-desktop.png` | `r2-triage-entry-form-tablet.png` |
| Triage validation state | `r2-triage-validation-errors-desktop.png` | `r2-triage-validation-errors-tablet.png` |
| Latest vital observations | `r2-latest-vital-observations-desktop.png` | `r2-latest-vital-observations-tablet.png` |
| Repeated-vitals history | `r2-repeated-vitals-history-desktop.png` | `r2-repeated-vitals-history-tablet.png` |
| Triage correction confirmation | `r2-triage-correction-confirmation-desktop.png` | `r2-triage-correction-confirmation-tablet.png` |
| Vital correction confirmation | `r2-vital-correction-confirmation-desktop.png` | `r2-vital-correction-confirmation-tablet.png` |
| Stale-version conflict | `r2-stale-version-conflict-desktop.png` | `r2-stale-version-conflict-tablet.png` |
| Permission denied | `r2-permission-denied-state-desktop.png` | `r2-permission-denied-state-tablet.png` |
| Loading state | `r2-loading-state-desktop.png` | `r2-loading-state-tablet.png` |
| Offline/API unavailable state | `r2-offline-api-unavailable-state-desktop.png` | `r2-offline-api-unavailable-state-tablet.png` |

Additional complete-workspace captures:

| View | File |
| --- | --- |
| Complete workspace, 1440 x 900 | `r2-case-workspace-desktop.png` |
| Complete workspace, tablet | `r2-case-workspace-tablet.png` |
| Complete workspace, 1920 x 1080 | `r2-complete-clinical-case-workspace-1920-desktop.png` |

The Playwright snapshot baselines for the full case workspace were also updated because the R2 documentation section legitimately changes the page height:

- `apps/web/e2e/clinical-slice.spec.ts-snapshots/case-workspace-desktop-win32.png`
- `apps/web/e2e/clinical-slice.spec.ts-snapshots/case-workspace-tablet-win32.png`
