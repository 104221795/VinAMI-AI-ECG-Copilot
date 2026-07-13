# Hướng Dẫn Đặt Hình

Tài liệu này là danh mục figure cho `VinAMI_ACS_MVP_Report.md` và bản DOCX. Các sơ đồ kiến trúc được giữ ở dạng Mermaid trong tài liệu nguồn; khi xuất bản, render chúng thành PNG hoặc SVG với cùng mã hình và thay thế đúng vị trí placeholder. Không dùng hình minh họa lâm sàng hoặc biểu đồ hiệu năng mới nếu không có nguồn artifact tương ứng.

| Mã | Vị trí báo cáo | Nguồn chính xác | Mục đích | Trạng thái |
|---|---|---|---|---|
| Hình 1 | Mục 3 | `docs/architecture/system-context.md`, Mermaid `VinAMI ACS Operating System - System Context` | Bối cảnh hệ thống | Cần render |
| Hình 2 | Mục 8 | `docs/architecture/container-view.md`, Mermaid `VinAMI ACS MVP - Container Diagram` | Containers MVP | Cần render |
| Hình 3 | Mục 8 | `docs/architecture/component-view.md`, Mermaid `Backend Component View` | Thành phần backend | Cần render |
| Hình 4 | Mục 9 | `docs/architecture/bounded-contexts.md`, Mermaid `Relationship Map` | Quan hệ bounded contexts | Cần render |
| Hình 5 | Mục 7 | `docs/architecture/sequence-flows.md`, Mermaid `Patient Arrival to Clinical Review` | Hành trình ca bệnh | Cần render |
| Hình 6 | Mục 13 | `docs/architecture/sequence-flows.md`, Mermaid `ECG Upload to AI Result` | Luồng ECG AI | Cần render |
| Hình 7 | Mục 15 | `docs/architecture/sequence-flows.md`, Mermaid `Troponin Result to Pathway Review` | Luồng troponin | Cần render |
| Hình 8 | Mục 17 | `docs/architecture/sequence-flows.md`, Mermaid `Cath-Lab Review Workflow` | Luồng review cath-lab | Cần render |
| Hình 9 | Mục 10 | `docs/architecture/sequence-flows.md`, Mermaid `Event Publication and Transactional Outbox` | Outbox | Cần render |
| Hình 10 | Mục 25 | `docs/architecture/deployment-view.md`, Mermaid `Deployment View` | Triển khai Compose | Cần render |
| Hình 11 | Phụ lục A | `VinStroke_ECG_artifacts/reports/inference_cwt_grid_9.png` | CWT input của prototype | Artifact sẵn có |
| Hình 12 | Phụ lục A | `VinStroke_ECG_artifacts/reports/per_class_auprc.png` | AUPRC theo nhãn | Artifact sẵn có |
| Hình 13 | Phụ lục A | `VinStroke_ECG_artifacts/reports/calibration_curve_macro.png` | Calibration prototype | Artifact sẵn có |

**Quy tắc caption:** Caption phải nói rõ nguồn, vai trò và giới hạn. Ví dụ: “Hình 11. CWT grid là đầu vào của checkpoint nghiên cứu; không phải ECG lâm sàng của VinAMI ACS.”

