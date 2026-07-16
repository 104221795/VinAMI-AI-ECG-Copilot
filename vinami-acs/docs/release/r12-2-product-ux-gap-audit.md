# R12.2 Product UX Consolidation and End-to-End Gap Audit

Date: 2026-07-16

## Scope

R12.2 consolidated the physician-facing product shell and audited the visible R0-R12 product paths without adding new clinical authority. The work focused on missing navigation, route reachability, stale/error resilience, and a truthful gap matrix for scheduling, AI, and automation.

VinAMI remains a research and engineering MVP. Demonstration workflow and reasoning rules are not for clinical use.

## UI/UX Issues Fixed

| Area                             | Issue                                                                                                                   | Resolution                                                                                                                             |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Case workspace navigation        | Triage and Vitals existed as a feature but had no case-level route in the main workspace navigation.                    | Added `/cases/[caseId]/documentation` and linked it from the case header, sidebar, and overview workspace.                             |
| Case header consistency          | Case-level header used inline spacing and inconsistent section ordering.                                                | Reworked the reusable case header with consistent breadcrumb, metadata chips, and ordered workspace links.                             |
| Sidebar information architecture | Selected-case sidebar omitted ECG, Troponin, and Triage/Vitals, forcing users to discover modules from different pages. | Added explicit selected-case navigation for Overview, Triage/Vitals, ECG, Troponin, Clinical Reasoning, Workflow, Timeline, and Audit. |
| Overview navigation              | The complete case workspace showed Triage and Vitals data but did not link to the owning documentation workspace.       | Added an owning-workspace link from the Triage/Vitals panel.                                                                           |
| Command Center resilience        | A background refetch failure could replace usable cached operational data with a full error state.                      | Preserved cached data and shows an inline critical banner with retry when a refetch fails after initial data exists.                   |
| Responsive polish                | Case metadata and workspace links could crowd at smaller widths.                                                        | Added CSS classes for wrapping metadata chips and compact workspace section controls.                                                  |

## R0-R12 Gap Matrix

| Milestone | Product path                              | Status                          | Evidence                                                                        | Gap                                                                                                     |
| --------- | ----------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| R0-R1     | Patient, encounter, case lifecycle        | Working for MVP paths           | Lifecycle API, seed data, idempotency, audit/timeline projections               | Not a production EHR identity or MPI integration.                                                       |
| R2        | Triage and vitals                         | Working, route fixed in R12.2   | Clinical documentation feature, API client, tests, new `/documentation` route   | No advanced nursing triage protocol engine.                                                             |
| R3-R4     | ECG evidence and dynamic ECG              | Working for demo/research paths | ECG workspace, import/demo flows, repeat ECG reminders, provider contract       | No production device/PACS integration; AI remains support only.                                         |
| R5        | Clinical reasoning and physician decision | Working for MVP                 | Reasoning workspace, effective decision display, revocation/correction handling | Rules are demonstration rules, not validated guideline implementation.                                  |
| R6        | Workflow, tasks, alerts                   | Working for MVP                 | Workflow operations workspace, persisted tasks/alerts, safety guards            | No hospital-wide escalation routing.                                                                    |
| R7        | Command Center                            | Working, UX hardened            | Active case queue, filters, selected quick view, real-time invalidation         | Summary counts are page-scoped where documented.                                                        |
| R8        | Complete case workspace                   | Working, UX linked              | Integrated case overview with owner links and safety wording                    | Does not duplicate full ECG waveforms, full lab history, or full audit by design.                       |
| R9        | Timeline, audit, outcome, learning        | Working for MVP                 | Timeline/audit/history panels and report/export paths                           | Outcome and learning are research-use records, not clinical registry reporting.                         |
| R10       | Real-time and integration foundation      | Working for simulated sources   | SSE notifications, integration status panel, simulated lab/ECG messages         | No production LIS/HIS/PACS connection.                                                                  |
| R11       | Operational frontend integration          | Working for current pages       | Next.js app shell, typed view models, generated API client patterns             | Some BFF/browser fetch paths remain direct for multipart or proxy flows.                                |
| R12       | Validation/release hardening              | Partial gate                    | Prior R12 report lists passing core gates and unresolved security tool gaps     | Bandit and pip-audit were unavailable locally; full screenshot baseline suite had known diffs/timeouts. |

## Scheduling Flow Status

| Capability                      | Status          | Notes                                                                                                                        |
| ------------------------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Repeat ECG reminder             | Working         | Implemented through ECG reminder endpoints and workspace actions.                                                            |
| Workflow due timers             | Working for MVP | Worker evaluates due workflow timers and outbox-driven updates.                                                              |
| Troponin follow-up timing       | Partial         | Serial troponin timing and overdue concepts exist, but no full appointment workflow.                                         |
| Outpatient follow-up scheduling | Missing         | Outcome records include follow-up status text, but there is no appointment model, slot calendar, or hospital scheduling API. |
| Calendar integration            | Missing         | No external calendar, HIS scheduling, or appointment-book adapter is implemented.                                            |

Conclusion: VinAMI has clinical timers and reminders, not a complete scheduling product.

## AI Path Status

| Capability               | Status                  | Notes                                                                                               |
| ------------------------ | ----------------------- | --------------------------------------------------------------------------------------------------- |
| ECG AI provider boundary | Working                 | Provider is accessed through the ECG AI port; workflow does not import model runtimes.              |
| Mock ECG provider        | Working                 | Deterministic demonstration provider with safe wording.                                             |
| Torch/ConvNeXt adapter   | Partial/evidence module | Existing research artifacts are treated as an ECG Intelligence prototype, not the product core.     |
| AI result display        | Working                 | UI uses "AI-supported finding" and model/provenance wording, not diagnosis or clinical probability. |
| AI authority             | Correctly blocked       | AI output does not create physician decisions or cath-lab authority.                                |

## Automation Status

| Automation                     | Status                    | Safety posture                                                         |
| ------------------------------ | ------------------------- | ---------------------------------------------------------------------- |
| Transactional outbox dispatch  | Working for MVP           | Notifications and projections are backend-authoritative and retryable. |
| Workflow effects               | Working under R6 rules    | Generates tasks/alerts through backend workflow policy only.           |
| Real-time updates              | Working for notifications | Browser refetches authoritative API data after receiving events.       |
| Autonomous diagnosis           | Not implemented           | Correctly absent.                                                      |
| Autonomous cath-lab activation | Not implemented           | Correctly absent; physician authority remains required.                |
| Automatic discharge/rule-out   | Not implemented           | Correctly absent; MVP rules are demonstration only.                    |

## Motion Audit

No Framer Motion package is installed. R12.2 did not add a new animation library. The current UI uses CSS transitions and respects existing reduced-motion CSS patterns. A future motion pass should only use an existing approved dependency or a documented ADR.

## Validation Performed

Focused checks were run after implementation:

- Frontend format/lint/type/test gate through `pnpm.cmd quality`.
- Python architecture boundary tests through `python -m pytest tests/architecture/test_dependency_rules.py`.
- Focused complete-case workspace unit coverage.
- Route and source scan for scheduling, AI, automation, and direct-fetch gaps.

See the sprint completion response for the exact command results.

## Known Gaps

- Full hospital scheduling is not implemented.
- Production hospital integrations are intentionally absent; only simulated connectors exist.
- Security tools from R12 remain environment-dependent if not installed locally.
- Some frontend flows still use BFF/direct fetch for backend proxy or multipart commands; this should be normalized where the generated client supports the shape.
- Motion remains CSS-only because no approved motion package is present.

## Recommendation

R12.2 is suitable as a product UX consolidation checkpoint. R13 can safely begin only if its scope acknowledges that scheduling and production integration remain separate product capabilities, not completed VinAMI core features.
