# Nguồn Dữ Liệu Và Bằng Chứng Của Báo Cáo

| Nhóm nội dung | Nguồn | Cách dùng trong báo cáo | Giới hạn |
|---|---|---|---|
| Product/safety charter | `docs/PROGRAM_CHARTER.md` | Positioning, nguyên tắc an toàn, scope | Là định hướng kiến trúc, không phải bằng chứng lâm sàng |
| Kiến trúc | `docs/architecture/*.md` | Context/container/component, domain, event, deployment, data | Blueprint Sprint 0, chưa là hệ thống đã chạy |
| Quyết định | `docs/adr/ADR-001` đến `ADR-006` | Lý do modular monolith, ports, outbox, safety | Quyết định MVP có thể được thay đổi bằng ADR mới |
| MVP contract | `docs/mvp/*.md` | Scope, use case, acceptance, risk, traceability | Mục tiêu kiểm thử, không phải kết quả triển khai |
| Prototype ECG | `Research/VinStroke_ECG_ConvNeXtV2_Report_Improved.md` | Phụ lục A, nền tảng AI module | Nghiên cứu PTB-XL; không phải ACS validation |
| Artifact configuration | `VinStroke_ECG_artifacts/config.json` | Backbone/labels/input setting của prototype | Không chứng minh hiệu năng lâm sàng |
| Artifact metrics | `VinStroke_ECG_artifacts/reports/test_metrics.csv`, `per_class_metrics.csv`, `calibration_metrics.csv`, `ablation_results.csv` | Bảng số liệu Appendix A | Internal PTB-XL test; ablation chưa hoàn tất |
| Artifact visual | `VinStroke_ECG_artifacts/reports/*.png` | Figure Appendix A theo guide | Heatmap là attention approximation, không phải causality |

Không có dữ liệu bệnh nhân thật, outcome ACS, pathway guideline được phê duyệt, hay validation lâm sàng nào được dùng để tuyên bố hiệu quả của VinAMI ACS MVP.

