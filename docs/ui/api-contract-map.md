# API Contract Map

| UI surface | Required API contract | Current status |
|---|---|---|
| Command Center queue | `GET /api/v1/clinical-cases` | Empty envelope only |
| Case Workspace | `GET /api/v1/clinical-cases/{id}` | Missing |
| ECG workspace | ECG study/result/explanation query and upload commands | Missing |
| Troponin timeline | case troponin query and result commands | Missing |
| Tasks, alerts, timeline, audit | filtered case queries and versioned commands | Missing |
