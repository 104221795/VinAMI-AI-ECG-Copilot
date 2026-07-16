# R4 Baseline - Serial Troponin Evidence

Date: 2026-07-14

## Runtime and repository state

- Branch: `frontend/f0-nextjs-clinical-slice`
- Commit at pre-flight: `e39f753`
- Existing R3 changes are intentionally preserved in the working tree.
- API `/health` returned healthy and the Next.js entry point returned HTTP 200.
- The existing troponin implementation is an early persistence prototype: it stores numeric values and reference limits as binary `float`, assumes same-assay comparisons, and has no case-level API or physician workspace.
- The existing `lab_results` records are not rewritten or represented as R4-normalized evidence.
- Docker CLI runtime inspection was blocked by sandbox access to the Docker named pipe during pre-flight; it is a required final-gate check.

## R4 starting classification

| Capability                      | Baseline                                                 |
| ------------------------------- | -------------------------------------------------------- |
| Decimal laboratory evidence     | Missing                                                  |
| Assay/version catalog           | Missing                                                  |
| Explicit unit conversion policy | Missing                                                  |
| Immutable amendment chain       | Missing                                                  |
| Laboratory connector            | Missing                                                  |
| Persisted import jobs and retry | Missing                                                  |
| Clinician troponin review       | Missing                                                  |
| Repeat-measurement lifecycle    | Missing                                                  |
| Transactional R4 outbox         | Missing                                                  |
| Case-level FastAPI contracts    | Placeholder only                                         |
| Next.js troponin workspace      | Missing                                                  |
| Live LIS integration            | Deferred; no live connector or credentials are available |

## Safety baseline

R4 is limited to technical laboratory evidence. It must not diagnose AMI, perform rule-in/rule-out, choose a pathway, recommend treatment, activate cath-lab review, or close a Clinical Case. Laboratory reference limits must be supplied with provenance and must never be inferred from memory.
