# Placeholder Inventory

## Clinical API Placeholders

`apps/api/app.py` registers 15 resource collections in a loop. Every handler returns:

```json
{
  "resource": "<resource-name>",
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": 0
}
```

The placeholder resources are patients, encounters, clinical-cases, triage, vitals, ecg-studies,
ecg-ai-results, troponin, pathways, workflows, tasks, alerts, timeline, audit, and model-registry.
None queries PostgreSQL.

## Empty Delivery Packages

All bounded-context `api/` packages are package markers. No context owns request DTOs, response
DTOs, routers, dependencies, error mappings, or OpenAPI examples.

Application packages that are markers only:

- Patient and Encounter
- ACS Clinical Case
- ECG Intelligence
- Clinical Reasoning
- Alerts and Escalation
- Timeline
- Audit
- Model Registry
- Identity and Access

Triage and Troponin have pure in-memory apply functions but no transaction handler. Workflow is the
only context with a real application command handler.

## Platform Responses That Do Not Prove Readiness

- `/health` is process liveness only.
- `/ready` executes `SELECT 1` and reports ready with zero application tables.
- Streamlit `/_stcore/health` reports `ok` without proving a browser session can import and render
  the script or retrieve clinical data.
- `scripts/seed.py` is a database probe and always reports `clinical_records_created=0`.

## AI Placeholders

- `MockECGAIProvider` returns deterministic scores but variable execution timestamps.
- No application service invokes the provider.
- No Torch/ConvNeXtV2 adapter exists in `vinami-acs`.
- The generic model-registry and ECG-result endpoints never return provider data.
- The preserved one-gigabyte ConvNeXtV2 checkpoint is outside the ACS product boundary.

## Identity Placeholder

Clinical user/team tables and value objects exist, but there is no identity provider, actor context,
credential handling, authorization, or endpoint permission placeholder. UUID actor fields alone do
not constitute identity or access control.

## Misleading Names or Tests

- `test_normal_rule_out_demo_requires_troponin_and_physician_confirmation` supplies a boolean
  `physician_decision_recorded` fact. It does not create a physician decision.
- `test_transfer_workflow_requires_physician_confirmation` relies on the same spoofable fact.
- The architecture test named `test_dashboard_does_not_import_database_sessions` checks only
  SQLAlchemy imports, not repositories, domain policies, or all prohibited imports.
- Integration migration setup loads every ORM mapping into the test process, masking production
  composition failures.

## Reproducibility Placeholder

The root `.gitignore` has a broad `models/` rule. It ignores
`vinami-acs/apps/dashboard/models/view_models.py`. The current local Docker context includes the
file, but a Git clone would not. No frontend code was modified by this audit.

## No Generic CRUD or Fake In-Memory Backend

No fake clinical in-memory backend or generic CRUD service was found. The primary issue is more
fundamental: the clinical API does not call any application or persistence code.
