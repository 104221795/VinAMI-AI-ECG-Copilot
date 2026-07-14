# F0 Performance Baseline

Measured from the optimized Next.js 15.5.20 build on 2026-07-13:

| Route                      | Route JS | First load JS |
| -------------------------- | -------: | ------------: |
| `/command-center`          |  42.2 kB |        180 kB |
| `/cases/[caseId]`          |  0.13 kB |        135 kB |
| `/cases/[caseId]/timeline` |  3.82 kB |        135 kB |
| `/cases/[caseId]/audit`    |  0.13 kB |        135 kB |
| `/system-health`           |  2.86 kB |        131 kB |

Shared first-load JavaScript is 103 kB. Every clinical/identity route is dynamically rendered. The build compiled in 16.0 seconds in the local validation environment. Browser lifecycle tests completed in 49.0 seconds for both desktop and tablet projects when run deterministically with one worker.

This is a bundle and test-runtime baseline, not a Web Vitals, throughput or production performance certification. R2 should add browser performance budgets and API latency observations after the joined queue projection exists.
