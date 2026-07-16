# R4 Completion Report

## Delivered

- Decimal-based immutable troponin evidence and assay catalog.
- Explicit conversion and technical compatibility policies.
- Manual entry, local/mock import, persisted failures, retry and duplicate suppression.
- Immutable amendments with effective-series selection.
- Clinician evidence review, immutable correction revisions, and clinician-originated repeat request lifecycle.
- Repeat-request acknowledge, complete and cancel controls with version/idempotency preconditions.
- Persisted deterministic source-delivery lifecycle: preliminary, final and amended revisions.
- Transactional R4 events projected through the existing outbox dispatcher to Timeline and Audit.
- Versioned FastAPI contracts and regenerated TypeScript OpenAPI client types.
- Physician-facing Next.js route `/cases/[caseId]/troponin` with latest result, trend, delta, assay/reference provenance, full history, import provenance, review and repeat-request state.
- Three bounded Playwright scenarios and two visual baselines.

## Gate status

R4.1 remains NO-GO for the strict acceptance gate. Static checks, 118 backend tests, 37 frontend tests, scoped application-service coverage at 80%, OpenAPI generation/drift, production builds, desktop Playwright journeys and a baseline axe-core workspace scan passed. The migration head is `e7c3a91b6f42`. However, the required axe matrix was not exercised for every specified dialog/state and the browser suite does not yet drive every repeat/correction command end-to-end. This is not a clinical-release gate.

## Safety statement

This research-use MVP records and displays numerical laboratory evidence. It does not diagnose AMI, make disposition decisions, select a pathway, recommend treatment, activate cath-lab review, or close a case. No guideline threshold was encoded. It is not clinically validated, production-ready, or suitable for patient care.

## Known limitations

- Connector is local/mock only; no live LIS, HL7 v2 endpoint or FHIR endpoint exists.
- Assay catalog entries are synthetic demonstrations and contain no manufacturer reference limits.
- Development identity is controlled but is not production authentication/authorization.
- Import processing is synchronous inside the command transaction; the connector boundary permits later worker extraction.
- Accessibility evidence is an automated axe-core scan of the R4 workspace, not formal accessibility certification.
- The required accessibility matrix still needs scans for manual entry, incompatible-assay, correction-dialog, repeat-transition-dialog, full source-revision history and import retry states; it is a release blocker for the strict R4.1 gate.

## R5 recommendation

NO-GO for R5 Clinical Reasoning until the remaining browser/accessibility acceptance matrix passes. R5 must consume normalized evidence contracts and must not add unapproved clinical thresholds.
