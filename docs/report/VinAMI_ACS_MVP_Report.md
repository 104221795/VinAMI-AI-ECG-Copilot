# VinAMI ACS Operating System

## Báo Cáo Sản Phẩm Và Kiến Trúc MVP

**Phiên bản:** Sprint 1 - Product and Architecture Report  
**Ngày:** 13/07/2026  
**Trạng thái:** Research and engineering MVP

> **Demonstration rule - not for clinical use.** VinAMI ACS không phải thiết bị y tế đã được thẩm định, không phải sản phẩm AMI rule-out, không tự kích hoạt cath-lab và không thay thế phán đoán của bác sĩ.

## Mục lục

_[Mục lục sẽ được Word cập nhật từ các Heading sau khi mở tài liệu.]_

## 1. Tóm tắt điều hành

VinAMI ACS Operating System là hệ thống điều phối công việc cho ca nghi ngờ hội chứng vành cấp. Sản phẩm tổ chức triệu chứng, vital signs, ECG, troponin, review task, alert và quyết định của con người quanh một clinical case có dòng thời gian và audit rõ ràng.

MVP là research and engineering MVP. Nó không chẩn đoán, không rule out AMI từ ECG, không triển khai production guideline và không tự đưa ra lệnh kích hoạt cath-lab. Mọi gợi ý quy tắc đều là demonstration rule có version, facts used, limitation và yêu cầu review.

Kiến trúc dùng modular monolith: FastAPI là system of record, PostgreSQL giữ nghiệp vụ/audit/outbox, Streamlit là API client và ECG AI là provider thay thế được. Điều này giúp workflow vẫn hoạt động khi model thay đổi, không có GPU hoặc provider lỗi.

## 2. Vấn đề workflow lâm sàng

Một ca nghi ngờ ACS tạo ra nhiều thông tin theo thời gian: lý do đến viện, triệu chứng, vital signs, ECG lặp lại, troponin tuần tự, nhận định bác sĩ và yêu cầu phối hợp. Rủi ro lớn không chỉ là thiếu thông tin mà còn là thiếu ngữ cảnh: kết quả nào đang được review, ai chịu trách nhiệm và quyết định nào đã có xác nhận.

MVP không tái tạo toàn bộ EHR. Nó tập trung vào case workspace, nơi mỗi evidence có provenance, mỗi task có owner, mỗi transition có audit và mỗi conflict dẫn tới review thay vì kết luận tự động.

## 3. Tầm nhìn sản phẩm

Tầm nhìn là operating system cho workflow ACS: tiếp nhận ca, tổ chức evidence, điều phối review, theo dõi decision và tạo dữ liệu có cấu trúc cho cải tiến sau này. Trong MVP, từng phần được tách bounded context để có thể thay đổi mà không kéo toàn bộ hệ thống theo.

[Hình 1: System context. Nguồn: `docs/architecture/system-context.md`, Mermaid “VinAMI ACS Operating System - System Context”.]

Cần phân biệt ba mức: **hiện tại** là blueprint/MVP kỹ thuật; **future capability** là EHR/LIS/identity/provider integrations; **clinical validation** là chương trình độc lập chưa bắt đầu. Không mức nào được suy ra từ mức trước.

## 4. Vì sao clinical workflow mới là sản phẩm

AI có thể thay đổi, thiếu input đúng contract, hoạt động chậm hoặc lỗi. Workflow vẫn phải tổ chức case, làm rõ evidence, tạo task, theo dõi review và ghi quyết định. Vì vậy AI chỉ là một evidence provider, không phải nguồn chân lý hay bộ điều khiển workflow.

Sản phẩm tập trung vào các câu hỏi cấp case: evidence nào đang có hoặc thiếu, dữ liệu nào mâu thuẫn, việc nào còn chờ, bác sĩ nào đã xác nhận, và lịch sử có audit được hay không.

## 5. Người dùng MVP dự kiến

| Người dùng | Nhu cầu trong MVP | Không được giả định |
|---|---|---|
| Điều dưỡng/tiếp nhận | Đăng ký encounter, facts và evidence | Không phải người đưa pathway cuối cùng |
| Bác sĩ | Review case, evidence, demo suggestion và confirmation | Không bị thay thế bởi score AI |
| Bác sĩ tim mạch | Nhận và hoàn tất review task | Không nhận activation tự động |
| Research/admin | Xem audit, model metadata, export summary | IAM production chưa tồn tại |

## 6. Phạm vi và safety boundaries

MVP gồm tạo suspected-ACS case, triage facts, ECG/troponin reference, mock ECG analysis, demonstration-rule assessment, task, alert, audit, timeline và research export. Scope hẹp này giúp safety invariants có thể được kiểm thử trước khi mở rộng.

| Trong scope | Ngoài scope |
|---|---|
| Evidence provenance, task/alert, demo rules | Diagnosis, AMI rule-out, medication/order recommendation |
| Mock provider, optional research adapter | Training/retraining, continuous telemetry, patient-facing use |
| API, PostgreSQL/outbox, API-only UI | Production EHR/LIS/identity, multi-site deployment |

Các rule không thương lượng: ECG không rule out AMI; AI không kích hoạt cath-lab; action hệ quả cần physician confirmation; conflict tạo review alert; AI result có model/version/time/input reference; transition có audit.

## 7. ACS case journey

Case được mở từ encounter; triage facts và evidence được thêm theo thời gian. ECG hoặc troponin không tự thay đổi outcome, nhưng có thể làm xuất hiện review request. Dashboard hợp nhất trải nghiệm, còn ownership của dữ liệu vẫn tách rõ.

[Hình 5: Patient arrival to clinical review. Nguồn: `docs/architecture/sequence-flows.md`, Mermaid “Patient Arrival to Clinical Review”.]

Journey gồm mở case, ghi symptoms/vitals, gắn ECG/troponin, yêu cầu AI, tạo assessment, sinh alert/task, physician confirmation, hoàn tất task và đóng case. Mỗi bước là command có actor, UTC timestamp, correlation ID và audit trail.

## 8. Kiến trúc hệ thống mười lớp

Mười lớp là cách đọc trách nhiệm: UI, API delivery, application commands/queries, domain, ports, adapters, persistence/UoW, outbox/event handlers, evidence/model providers, và observability/security controls. Đây không phải mười microservice.

[Hình 2: Container view. Nguồn: `docs/architecture/container-view.md`, Mermaid “VinAMI ACS MVP - Container Diagram”.]

[Hình 3: Backend component view. Nguồn: `docs/architecture/component-view.md`, Mermaid “Backend Component View”.]

FastAPI là interface system of record. Streamlit gọi `/api/v1`; PostgreSQL giữ write model, outbox, audit và read projections; object storage giữ reference đến evidence lớn. Dispatcher đảm bảo event đi cùng state change mà chưa cần Kafka hay distributed system.

## 9. Domain-Driven Design

DDD được dùng để không biến sản phẩm thành tập bảng CRUD. Patient/Encounter sở hữu reference; Triage sở hữu facts; ECG/Troponin sở hữu evidence; Clinical Reasoning sở hữu evaluation; Workflow sở hữu task/confirmation; Audit sở hữu chronology bất biến.

[Hình 4: Bounded-context relationship map. Nguồn: `docs/architecture/bounded-contexts.md`, Mermaid “Relationship Map”.]

Aggregate là ranh giới consistency: `ClinicalCase` kiểm soát lifecycle, `ECGStudy` kiểm soát immutable input reference, `ClinicalTask` kiểm soát completion provenance. Contexts chỉ trao đổi ID, DTO và versioned event, không import domain aggregate/ORM của nhau.

## 10. Event-Driven Architecture

Domain event là bản ghi rằng một sự việc nghiệp vụ đã xảy ra, như `ECGUploaded.v1` hoặc `TaskCompleted.v1`. Event envelope có event ID, aggregate/version, actor, UTC time, correlation/causation ID, schema version và payload.

[Hình 9: Event publication and transactional outbox. Nguồn: `docs/architecture/sequence-flows.md`, Mermaid “Event Publication and Transactional Outbox”.]

State change và outbox envelope được commit trong cùng transaction. Dispatcher xử lý at-least-once; handler deduplicate theo `event_id`, lưu processing outcome và không bỏ qua lỗi âm thầm. Sau này có thể gắn broker như một consumer mới mà không đổi aggregate behavior.

## 11. Patient và Encounter Management

MVP lưu local patient reference và encounter context tối thiểu để mở case, không tuyên bố thay thế EHR hay thành master patient index. `Patient` và `Encounter` tách riêng để một patient có thể có nhiều encounter, còn mỗi ACS case gắn một encounter rõ ràng.

`RegisterPatient`, `StartEncounter` và `OpenClinicalCase` là commands chính. UUID được dùng xuyên suốt; source/capture time được giữ tách với system timestamp khi cần.

## 12. Triage

Triage ghi facts chứ không suy luận bệnh. `SymptomsRecorded` giữ symptom snapshot với provenance; `VitalsRecorded` giữ vital set, time và measurement source. Đây là phân biệt quan trọng giữa dữ liệu quan sát và kết luận hệ thống.

Triage facts là input cho Clinical Reasoning nhưng không chứa rule engine. Thay đổi ruleset không sửa lịch sử facts, và UI không tự tính logic lâm sàng trong form.

## 13. ECG Intelligence

ECG Intelligence quản lý `ECGStudy`, immutable input reference, quality assessment, `AIAnalysis`, normalized output, explanation reference và model provenance. `ECGAIProvider` chỉ có `predict()`, `explain()`, `health()` và `get_model_info()`; business logic không import torch, timm, ONNX Runtime hay checkpoint.

[Hình 6: ECG upload to AI result. Nguồn: `docs/architecture/sequence-flows.md`, Mermaid “ECG Upload to AI Result”.]

MVP mặc định dùng deterministic `MockECGAIProvider` để workflow/safety tests chạy không cần GPU. `TorchECGAIProvider` tương lai đọc artifact ConvNeXtV2 ở chế độ read-only và chỉ trả normalized contract. AI result là evidence kèm limitation, không phải diagnosis và không tạo cath-lab action.

## 14. Dynamic ECG

Dynamic ECG trong VinAMI nghĩa là tổ chức ECG theo diễn tiến case: nhiều study, quality state, timestamp, evidence reference, analysis version và repeat-ECG task. Nó không có nghĩa MVP đã nhận continuous telemetry hoặc streaming waveform từ thiết bị.

`RepeatECGRequested.v1` và `RepeatECGDue.v1` giữ work item rõ ràng. Study mới được gắn vào case với provenance riêng thay vì ghi đè study trước. Streaming, waveform comparison lâm sàng và realtime alert là future capability cần protocol/data-quality/validation riêng.

## 15. Troponin Intelligence

Troponin Intelligence quản lý series measurement: ordered, collected, resulted, value, unit, source, time và delta. Delta phải chỉ rõ hai measurement nguồn và calculation version; hệ thống không tạo con số không truy vết được.

[Hình 7: Troponin result to pathway review. Nguồn: `docs/architecture/sequence-flows.md`, Mermaid “Troponin Result to Pathway Review”.]

MVP không hard-code guideline threshold từ trí nhớ. Nếu demonstration rule dùng điều kiện, ruleset/version và facts đầu vào phải hiển thị lại. LIS chỉ là future adapter; hiện tại clinician hoặc deterministic seed data cung cấp record có provenance.

## 16. Clinical Reasoning

Clinical Reasoning nhận facts chuẩn hóa từ case, triage, ECG và troponin để tạo `ClinicalPathwayAssessment`. Output gồm ruleset version, facts used, rule evaluations, conflict flags, wording của gợi ý và review requirement; nó không có quyền sửa workflow trực tiếp.

Mọi output hiển thị **Demonstration rule - not for clinical use.** Conflict không được che bởi score AI; nó dẫn tới review alert và physician-review request. Đây là behavior an toàn có thể test, không phải tuyên bố clinical accuracy.

## 17. Workflow Orchestration

Workflow biến review need thành work item có task type, assignee, due time, status và completion provenance. `PhysicianReview` là aggregate riêng để action hệ quả có actor, time, decision, reason và evidence reference.

[Hình 8: Cath-lab review workflow. Nguồn: `docs/architecture/sequence-flows.md`, Mermaid “Cath-Lab Review Workflow”.]

`CathLabReviewRequested.v1` chỉ được tạo sau physician confirmation và chỉ có nghĩa request review/task. Nó không phải cath-lab activation. Thiếu confirmation phải sinh structured error rõ ràng.

## 18. Command Dashboard

Command dashboard là case workspace, không phải bảng điều khiển điều trị. Nó ưu tiên case/encounter, evidence đang có, conflicts, task/alert mở, assessment có disclaimer, physician confirmation và timeline. Người dùng đi tới raw evidence/model metadata thay vì chỉ nhìn một score tổng.

Dashboard dùng query/read model; button command gọi API versioned, gửi command ID/expected version khi cần và hiển thị structured error như thiếu confirmation, invalid evidence reference hoặc provider unavailable.

## 19. Human-in-the-Loop Safety

Human-in-the-loop là invariant domain: AI output không gây action hệ quả; task có assignee; alert có acknowledgement; physician decision có typed provenance; mọi transition có audit event.

| Safety control | Cơ chế | Hành vi MVP |
|---|---|---|
| Không ECG-only rule-out | Clinical Reasoning constraint | Không có outcome rule-out |
| Không AI cath-lab activation | Provider/domain boundary | AI chỉ tạo evidence/review request |
| Physician confirmation | `PhysicianReview` | Chặn cath-lab review/transfer nếu thiếu |
| Conflict review | Alert/Task handlers | Raise alert và review task |
| Audit | Outbox + append-only audit | Actor/time/correlation/version |

## 20. Timeline và Audit

Timeline là read model theo UTC phục vụ case review. Audit là append-only record về command, actor, aggregate, event, state transition và delivery result. Timeline ưu tiên usability; audit ưu tiên truy vết.

Không có command xóa audit. Amendment tương lai phải tạo record/audit mới thay vì rewrite history, đặc biệt khi case có nhiều ECG, serial troponin hoặc decision thay đổi.

## 21. Learning Platform

Model Registry and Learning Data không khiến MVP thành hệ thống học liên tục. Registry ghi model name/version, input contract, capability, artifact digest/reference và health metadata. `AIAnalysisCompleted.v1` mang provenance để output biết model nào tạo ra nó.

Learning-data reuse mặc định tắt. Bất kỳ reuse nào cần governance, de-identification, retention, authority phù hợp, data quality protocol và ADR riêng. PTB-XL prototype là research evidence, không phải training pipeline cho ca VinAMI.

## 22. Data Model

| Aggregate | Khóa | Dữ liệu sở hữu | Invariant |
|---|---|---|---|
| Patient / Encounter | UUID | local reference, encounter metadata | Không là EHR master record |
| ClinicalCase | UUID + version | lifecycle, reason, evidence links | Gắn một encounter |
| TriageAssessment | case ID | symptoms, vitals, provenance | Facts không là diagnosis |
| ECGStudy / AIAnalysis | UUID | input/quality/result/provenance | Input immutable; model metadata đủ |
| TroponinSeries | case ID | measurements/deltas | Unit/time/source/formula rõ |
| Task / Review / Alert | UUID | work, confirmation, alert history | Action hệ quả cần confirmation |
| AuditEntry | UUID | audit chronology | Append-only |

Large evidence không nằm trực tiếp trong transaction rows. Database giữ metadata/immutable reference, object storage adapter giữ binary phù hợp.

## 23. API và Integration Strategy

FastAPI cung cấp `/api/v1` cho commands/queries. Router chỉ validate schema, gọi inbound port và map structured errors; không query ORM, không gọi provider và không chứa clinical rule.

EHR/registration, LIS, object storage, identity và ECG AI đều là outbound ports. MVP dùng manual/mock implementation. Integration thật cần contract test, provenance mapping và ADR cho semantics của từng nguồn.

## 24. UI Component Architecture

Streamlit ACS UI là delivery client. Components gồm case list/header, triage form, evidence panel, ECG analysis panel, troponin series, assessment, task/alert queue, physician decision form, timeline/audit và export action. Mỗi component chỉ đọc DTO hoặc gửi command tới API.

UI không import SQLAlchemy, repository, aggregate, policy hay provider. Đây là khác biệt có chủ ý với VinStroke research workspace cũ, nơi UI đọc research artifacts trực tiếp. Hai UI không được trộn.

## 25. Security và Observability

Patient references, evidence, symptoms, vitals, troponin và physician decision là restricted clinical data. Logs chỉ chứa correlation/event ID, error code và metadata an toàn; không chứa raw ECG, symptom text, token hoặc credentials.

[Hình 10: Deployment view. Nguồn: `docs/architecture/deployment-view.md`, Mermaid “Deployment View”.]

Observability ưu tiên structured logs, health/readiness, outbox delivery status, retry/failure state và audit query. Production HA, secrets, backup/restore, encryption keys và retention policy còn là unresolved work.

## 26. Testing Strategy

Domain unit tests kiểm tra invariants/safety gates; application tests dùng fake ports; repository/outbox tests chạy PostgreSQL; API contract tests kiểm tra schema/error; UI tests kiểm tra API-only behavior; integration tests kiểm tra provider/storage adapters.

Tests không đo clinical effectiveness. Chúng xác minh duplicate command không tạo duplicate task, provider fail sinh `AIAnalysisFailed`, thiếu physician confirmation bị chặn, mutation có audit/outbox và UI không có direct database dependency.

## 27. MVP Acceptance Criteria

MVP chỉ hoàn thành khi criteria trong `docs/mvp/acceptance-criteria.md` pass: valid encounter trước case, atomic outbox, idempotency, AI provenance, structured failure, safety gates, conflict alert, confirmation gate, API-only UI, timeline/audit và preservation của prototype research.

Đây là software acceptance, không phải clinical acceptance. Test pass không chứng minh model hay workflow an toàn cho bệnh nhân.

## 28. Demo Scenarios

| Scenario | Dữ liệu demo | Expected behavior |
|---|---|---|
| Ca mới | Deterministic patient/encounter seed | Case, audit/outbox, dashboard rõ |
| AI thành công | Mock hoặc research adapter | Provenance/limitation; không auto outcome |
| Provider lỗi | Mock failure contract | `AIAnalysisFailed`, error/retry rõ |
| Serial troponin | Hai measurement có unit/time | Delta truy vết nguồn; demo rule |
| Evidence conflict | ECG/troponin/triage facts | Alert + physician task, không kết luận |
| Cath-lab review | Confirmation có/không | Có thì request/task; thiếu thì reject |
| Export | Case demo có audit | Research summary có disclaimer |

## 29. Rủi ro và Giảm thiểu

Rủi ro lớn là diễn giải quá mức: coi demo rule như guideline, research model như ACS model, task review như activation. Mitigation nằm trong wording, domain invariant, API boundary, audit và explicit limitation, không chỉ ở UI.

Rủi ro kỹ thuật gồm duplicate event, handler failure, provider unavailability, optimistic-lock conflict, sensitive logs và mutation research artifact. Blueprint yêu cầu idempotency, outbox processing state, structured errors, expected-version command, redaction policy và read-only artifact mount.

## 30. Roadmap

| Giai đoạn | Mục tiêu | Điều kiện đi tiếp |
|---|---|---|
| Sprint 1 implementation | Python 3.12, Compose, Postgres/Alembic, Patient/Case/Audit | Outbox/audit/API tests pass |
| Sprint 2 workflow | Triage, task/alert, deterministic demo cases | Safety gate/UI API-only pass |
| Sprint 3 evidence | ECG/Troponin ports, mock provider, registry metadata | Provenance/error contract pass |
| Sprint 4 reasoning | Versioned demo rules, conflicts, physician review | No rule-out/no activation tests pass |
| Later research | Optional Torch adapter, integration contracts | ADR, governance, validation protocol |
| Clinical program | Validation/governance/regulatory work riêng | Không suy ra từ MVP completion |

## 31. Kết luận

VinAMI ACS được định nghĩa là workflow product có khả năng tổ chức evidence và trách nhiệm quanh ca nghi ngờ ACS. Modular monolith, DDD, ports/adapters, transactional outbox và API-only UI tạo kỷ luật kỹ thuật mà không phóng đại khả năng lâm sàng.

ECG AI là evidence provider thay thế được. Một MVP tốt phải thể hiện điều đó bằng kiến trúc và UI: không rule out, không activation tự động, luôn provenance, conflict review và physician confirmation. Nền tảng này tạo điều kiện cho nghiên cứu, integration và validation sau này diễn ra có kiểm soát.

# Appendix A: Existing CWT ConvNeXtV2 ECG Prototype

VinStroke-ECG là evidence cho một ECG Intelligence research module, không phải sản phẩm VinAMI ACS. Notebook Kaggle có 61 cells, dùng PTB-XL 12-lead 10 giây ở 100 Hz, CWT grid, ConvNeXtV2-Base và năm superclass `NORM`, `MI`, `STTC`, `CD`, `HYP`. `AFIB` có trong artifact stats nhưng không phải output head đã train của checkpoint hiện tại.

| Dữ liệu/đánh giá | Giá trị artifact | Diễn giải đúng |
|---|---:|---|
| Records có target | 21.430 | PTB-XL prepared manifest |
| Unique patients | 18.637 | De-identified research dataset |
| Split train/val/test | 17.111 / 2.156 / 2.163 | Fold-derived internal split |
| Macro AUROC | 0,886 | Internal test discrimination của 5 superclass |
| Macro AUPRC | 0,730 | Internal test với imbalance |
| Macro F1 | 0,669 | Thresholded internal result |
| CWT ablation row | 1 row | Không có CWT-STFT comparison công bằng |

[Hình 11: CWT model input. Nguồn: `VinStroke_ECG_artifacts/reports/inference_cwt_grid_9.png`. Artifact PTB-XL, không phải evidence bệnh nhân VinAMI ACS.]

| Nhãn | AUROC | AUPRC | F1 | Giới hạn |
|---|---:|---:|---:|---|
| NORM | 0,932 | 0,906 | 0,841 | Mạnh nhất trong thí nghiệm này |
| MI | 0,862 | 0,696 | 0,649 | PTB-XL superclass, không phải AMI diagnosis |
| STTC | 0,919 | 0,797 | 0,706 | ECG pattern group |
| CD | 0,895 | 0,793 | 0,702 | ECG pattern group |
| HYP | 0,824 | 0,456 | 0,451 | Evidence yếu hơn, cần review thận trọng |

[Hình 12: AUPRC theo nhãn. Nguồn: `VinStroke_ECG_artifacts/reports/per_class_auprc.png`.]

Calibration artifact cho thấy HYP có ECE 0,144, cao nhất trong năm nhãn; score không được trình bày như certainty lâm sàng. Grad-CAM-style outputs chỉ là attention approximation trên CWT grid, không phải lesion localization hay causal explanation.

[Hình 13: Macro calibration. Nguồn: `VinStroke_ECG_artifacts/reports/calibration_curve_macro.png`.]

PTB-XL không có ACS outcome, symptoms, serial troponin, ED diagnosis hay cath-lab outcome. Vì vậy prototype không thể là ACS/AMI triage system. Torch adapter tương lai chỉ chuyển output sang normalized evidence contract có model version, timestamp và input reference.

# Appendix B: Event Catalog

| Nhóm | Events v1 |
|---|---|
| Patient/case | `PatientRegistered`, `EncounterStarted`, `ClinicalCaseOpened`, `CaseClosed` |
| Triage | `SymptomsRecorded`, `VitalsRecorded` |
| ECG | `ECGUploaded`, `ECGQualityAssessed`, `AIAnalysisRequested`, `AIAnalysisCompleted`, `AIAnalysisFailed` |
| Troponin | `TroponinOrdered`, `TroponinCollected`, `TroponinResulted` |
| Reasoning | `ClinicalPathwaySuggested`, `PhysicianReviewRequested` |
| Workflow | `RepeatECGRequested`, `RepeatECGDue`, `PhysicianDecisionRecorded`, `TaskCreated`, `TaskCompleted`, `CathLabReviewRequested`, `TransferRequested` |
| Alerts | `AlertRaised`, `AlertAcknowledged`, `AlertResolved` |

Mọi event dùng envelope có event ID/type, occurred time, aggregate ID/version, correlation/causation, actor, schema version và payload. Xem `docs/architecture/event-catalog.md` để có payload/consumer.

# Appendix C: Data Dictionary

| Thuật ngữ | Nghĩa trong VinAMI MVP |
|---|---|
| PatientReference | Local reference tối thiểu; không phải EHR master identity |
| Encounter | Context của một lần tiếp cận; liên kết case |
| ClinicalCase | Aggregate lifecycle cho ca nghi ngờ ACS |
| EvidenceReference | URI/key immutable, media type, checksum/provenance khi có |
| ECGStudy | Metadata/reference một ECG; có thể nhiều study trong case |
| AIAnalysis | Normalized output kèm model provenance/limitation |
| TroponinMeasurement | Value/unit/source/collection-result time có provenance |
| TroponinDelta | Kết quả từ hai measurement, formula/version rõ |
| RulesetVersion | Phiên bản demonstration rules, không là guideline engine |
| ClinicalTask | Work item có owner/status/due/completion provenance |
| PhysicianConfirmation | Actor/time/reason/evidence reference cho action hệ quả |
| ClinicalAlert | Review/safety alert có source/status/acknowledgement |
| AuditEntry | Append-only record về command/event/transition |
| ModelProvenance | Model/provider/version/time/input reference |

# Appendix D: Traceability Matrix

| Requirement | Architecture control | Acceptance check |
|---|---|---|
| ECG không rule out AMI | Reasoning safety constraint | Không có rule-out outcome/API path |
| AI không activate cath lab | Provider boundary + Workflow gate | AI không đổi cath-lab state |
| Physician confirmation | `PhysicianReview` | Thiếu confirmation bị reject |
| Conflict phải review | Alert/Task handlers | Alert + review task xuất hiện |
| Prediction provenance | `AIAnalysis` + Model Registry | Provider/model/version/time/input đủ |
| Audit transition | UoW + outbox + audit | Mutation có audit/outbox |
| UI API-only | ADR-005 | Không DB/domain/provider import UI |
| Prototype preserved | Read-only adapter boundary | Artifact không bị ACS runtime sửa |

