# R4 Test Report

Date: 2026-07-14

## Focused validation

| Check                             | Result                                            |
| --------------------------------- | ------------------------------------------------- |
| Full backend suite                | 118 passed                                        |
| Scoped R4 application service     | 10 passed; 80% line coverage                      |
| Ruff focused check                | Passed after formatting                           |
| Mypy focused check                | Passed after protocol/narrowing fixes             |
| TypeScript typecheck              | Passed                                            |
| Next.js production build          | Passed; Troponin route 7 kB                       |
| OpenAPI generation/drift          | Passed                                            |
| Playwright R4                     | 3 passed                                          |
| Frontend Vitest                   | 37 passed across 11 files                         |
| Axe-core R4 workspace             | Passed at desktop and tablet widths               |
| Desktop/tablet visual inspection  | Passed; no overlap or clipping observed           |
| Decimal smoke                     | `12.3400000001` persisted and read back unchanged |
| API readiness                     | Ready at revision `e7c3a91b6f42`                  |
| Outbox                            | 0 dead letters; Timeline/Audit projections stored |
| Persisted R4 evidence             | 3 history, 2 effective, 1 delta, 1 review/request |

## Browser scenarios

1. Serial workspace at desktop and tablet, persistence and one-result state.
2. Deterministic preliminary/final/amended import lifecycle and duplicate delivery suppression.
3. Unsupported-unit HTTP 422 and stale amendment rejection; absence of cath-lab/treatment/model-diagnosis controls.

## Defects fixed during gate

- OpenAPI DTO name collision between ECG and Troponin `ImportBody`.
- Mock parser `external_result_id` was not mapped to the domain source identifier.
- Strict text locator ambiguity in the safety notice.
- Alembic index metadata differed from the migration declarations.
- Source-delivery uniqueness initially prevented a final or amended source revision from being stored.
- Review correction response fields were initially serialized on a troponin-result response.

The complete repository gate results are recorded in `r4-completion-report.md`; this document does not claim clinical validation.
