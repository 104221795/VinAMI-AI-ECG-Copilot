# Bounded Context Status

Status definitions:

- **Working:** executable through an application boundary with persistence and tests.
- **Partial:** meaningful internal code exists but the use case is incomplete or unexposed.
- **Placeholder:** a package/endpoint exists but provides no product behavior.
- **Failing:** an implemented path fails in the audited runtime or violates a safety invariant.
- **Missing:** no executable implementation exists.

| Bounded context | Status | Implemented truth | Critical gaps |
|---|---|---|---|
| Patient and Encounter | Partial | Aggregates, repository ports/adapters, tables, uniqueness, domain events; domain/UoW persistence verified. | No application handlers or API; no actor/correlation propagation; patient/encounter events have no audit handler. |
| ACS Clinical Case | Partial | Aggregate, optimistic version, repository, table, open/close events. | No application/API; list is placeholder; close is not coordinated with workflow, troponin, physician decision, or alerts. |
| Triage | Partial | `TriageAssessment`, symptoms, vitals, pure apply functions, observation tables. | No repository/UoW/API; `DataStatus` is not persisted; structured clinical fields are encoded as generic symptoms. |
| ECG Intelligence | Partial | Study aggregate, quality enum, normalized domain result, provider port, deterministic-score mock, relational result/finding mappings. | No orchestration or API; no upload store; no request/failure lifecycle; quality does not block `record_ai_result`; no Torch adapter; provider contract fields are not fully persisted. |
| Dynamic ECG | Missing | Repeat-ECG task/timer names exist in workflow. | No serial ECG aggregate/query, comparison, acquisition sequence, change detection, or case-level API. |
| Troponin Intelligence | Partial | Assay/measurement/timeline/delta domain, pure commands, repository and lab tables. | No application transaction/API/timer engine; persistence discards manufacturer, analyzer, reference limit, quality flags and renal context; order/collection times are replaced by adapter `now`. |
| Clinical Reasoning | Partial | Seven-pathway demo engine, decision trace types, pathway/risk tables. | No application handler, persisted rule registry/version, event integration, API, or approved rule artifact; hard-coded behavior exists; notice text is mojibake in engine. |
| Workflow and Tasks | Failing | Declarative JSON state graph, guards/effects, command receipts, timers, task/alert effects, optimistic version tests. | Production workflow creation fails from incomplete ORM registry; caller can forge physician-decision fact; no API; no actor requirement; case state is disconnected. |
| Alerts and Escalation | Partial | Alert aggregate/repository/table and workflow-generated alert persistence design. | No application/API/escalation policy; `resolve()` emits no `AlertResolved.v1`; workflow imports alert ORM directly; runtime workflow path fails. |
| Timeline and Audit | Failing | Tables, source-event uniqueness, projection handler, event envelope metadata. | Default case projection dead-letters at runtime; patient/encounter events have no handlers; no query ports/application/API. |
| Model Registry and Learning Data | Partial | Registry aggregate, repository/table, mock provider `ModelInfo`. | No application/API, active-model query, health snapshots, learning-data governance, seed, or save operation after activation. |
| Identity and Access | Placeholder | User/team value objects and tables. | No actor-context port, authentication, authorization, repository/use cases, API, or endpoint permission boundary. |

## Application Layer Inventory

| Context | Application implementation |
|---|---|
| Workflow | Real command handler and timer service, but runtime composition fails. |
| Triage | Pure domain apply functions only; no UoW or persistence orchestration. |
| Troponin | Pure domain apply functions only; no UoW or persistence orchestration. |
| Patient, Case, ECG, Reasoning, Alerts, Timeline, Audit, Model Registry, Identity | Package marker only. |

## Cross-Context Consistency

- `ClinicalCase` and `ClinicalWorkflow` have separate state models with no implemented
  application coordinator.
- Workflow persists alert records by importing the Alerts adapter directly. This contradicts the
  documented event/contract boundary.
- Reasoning results do not invoke workflow or alerts through a product handler.
- ECG and troponin facts are never normalized into workflow facts by an application service.
- Timeline/Audit is not a reliable downstream context because its default handler currently
  dead-letters.

## Conclusion

No bounded context is complete at the product boundary. Patient/Encounter and selected persistence
components are the strongest reusable pieces. Workflow and Timeline/Audit are classified as
failing because their production composition was executed and failed, not merely because their API
is absent.
