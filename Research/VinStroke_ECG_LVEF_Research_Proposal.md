# VinStroke-ECG-LVEF: Ước lượng Phân suất tống máu thất trái (LVEF) từ ECG 12 chuyển đạo bằng Deep Learning

## 1. Tóm tắt đề xuất nghiên cứu

Đề tài đề xuất mở rộng framework VinStroke-ECG sang bài toán ước lượng phân suất tống máu thất trái (**LVEF – Left Ventricular Ejection Fraction**) trực tiếp từ tín hiệu ECG 12 chuyển đạo, không cần siêu âm tim.

LVEF là chỉ số cốt lõi để chẩn đoán và phân loại suy tim (heart failure with reduced ejection fraction – **HFrEF**, LVEF ≤ 40%), nhưng hiện chỉ đo được bằng siêu âm tim (echocardiography) hoặc các phương tiện chẩn đoán hình ảnh khác — chi phí cao, cần kỹ thuật viên chuyên môn và không sẵn có ở tuyến y tế cơ sở. Trong khi đó, ECG là xét nghiệm rẻ, nhanh, phổ biến ở hầu hết các cơ sở y tế.

Nghiên cứu mốc của Attia et al. (Mayo Clinic, *Nature Medicine* 2019) đã chứng minh một mạng CNN học từ ECG 12 chuyển đạo có thể phát hiện LVEF ≤ 35% với AUC ≈ 0.93, sensitivity ≈ 82.5%, specificity ≈ 86.8%. Đề tài này kế thừa hướng tiếp cận đó, nhưng đặt trong bối cảnh hạ tầng đã có của VinStroke-ECG: pipeline tiền xử lý ECG, các biểu diễn CWT/STFT, 12-lead grid và các backbone (1D-ResNet, InceptionTime, ConvNeXtV2) đã được xây dựng và benchmark trên PTB-XL.

**Điểm khác biệt quan trọng nhất so với VinStroke-ECG gốc:** bài toán LVEF không phải là bài toán phân loại chẩn đoán ECG thông thường mà là bài toán sàng lọc dựa trên nhãn **ngoài ECG** (echo-derived), do đó thách thức lớn nhất không nằm ở kiến trúc mô hình mà nằm ở **việc xây dựng bộ dữ liệu ECG–LVEF ghép cặp**, vì hiện tại toàn bộ dataset đang có trong project (PTB-XL, Chapman, Georgia, CPSC2018, PTB, INCART, ACS_ECG nội bộ) đều **không có nhãn LVEF**.

**Phạm vi MVP (đã chốt):** thay vì đồng thời làm hồi quy LVEF (%) và sàng lọc nhị phân, MVP chỉ tập trung trả lời đúng **một câu hỏi**: *"Bệnh nhân này có LVEF ≤ 40% hay không?"* — bám sát đúng thiết kế của Attia et al. (2019) và tận dụng được cả các báo cáo siêu âm tim chỉ mô tả định tính (không có số LVEF chính xác), vì loại report này vẫn đủ để gán nhãn nhị phân dù không dùng được cho hồi quy. Việc thu hẹp phạm vi giúp tăng lượng dữ liệu khả dụng, đơn giản hóa đánh giá (so sánh trực tiếp với AUC ≈ 0.93 của Mayo Clinic) và dễ trình bày với đối tác lâm sàng hơn.

## 2. Tên đề tài

### Tên tiếng Việt

**VinStroke-ECG-LVEF: Ước lượng phân suất tống máu thất trái từ ECG 12 chuyển đạo bằng học sâu**

### Tên tiếng Anh

**VinStroke-ECG-LVEF: Deep Learning Estimation of Left Ventricular Ejection Fraction from 12-Lead ECG**

### Tên ngắn gọn

**VinStroke-ECG-LVEF**

## 3. Bối cảnh và động cơ nghiên cứu

Suy tim là một trong những nguyên nhân nhập viện hàng đầu, và LVEF là chỉ số then chốt để phân loại suy tim (HFrEF, HFmrEF, HFpEF) cũng như quyết định điều trị (chỉ định thuốc, thiết bị cấy ghép, tiên lượng). Tuy nhiên, siêu âm tim — phương tiện tiêu chuẩn để đo LVEF — đòi hỏi thiết bị, bác sĩ/kỹ thuật viên chuyên khoa tim mạch và thời gian, nên không phải lúc nào cũng sẵn có, đặc biệt ở tuyến y tế cơ sở hoặc trong tầm soát cộng đồng.

ECG 12 chuyển đạo, ngược lại, là xét nghiệm rẻ, nhanh, không xâm lấn và đã phổ biến rộng rãi. Nhiều nghiên cứu (Attia et al. 2019; Yao et al. 2021, JAMA; các nghiên cứu tái lập trên MIMIC-IV-ECG) đã cho thấy tồn tại tín hiệu điện học đủ mạnh trong ECG để suy luận gián tiếp về chức năng co bóp thất trái, dù cơ chế sinh lý bệnh học đầy đủ vẫn chưa được hiểu rõ hoàn toàn (mô hình học các pattern liên quan đến giãn buồng tim, rối loạn dẫn truyền, thay đổi trục điện tim... tương quan với LVEF thấp).

Về mặt hạ tầng, project VinStroke-ECG hiện đã có: pipeline tiền xử lý ECG, sinh biểu diễn CWT/STFT, cấu trúc 12-lead grid, nhiều backbone đã huấn luyện và benchmark (ResNet18, InceptionTime, TCN, xresnet1d101, ConvNeXtV2...). Đây là nền tảng thuận lợi để mở rộng sang bài toán LVEF **nếu giải quyết được vấn đề dữ liệu nhãn**.

## 4. Khoảng trống nghiên cứu (bao gồm khoảng trống dữ liệu nội bộ)

Rà soát toàn bộ dữ liệu và tài liệu hiện có trong project cho kết quả:

* `data/ptb-xl/ptbxl_database.csv` — có tuổi, giới, `scp_codes`, `heart_axis`, `infarction_stadium`... **không có LVEF**.
* `data/acs_ecg/CSV/*.csv` — có nhãn AMI/OMI/STEMI/NSTEMI/CTO/PCI/VF_VT... **không có LVEF**.
* Chapman, Georgia, CPSC2018, PTB, St Petersburg INCART — các bộ PhysioNet chuẩn, không đi kèm dữ liệu siêu âm tim.
* `Research/VinStroke_ECG_Research_Proposal.md` và các báo cáo ConvNeXtV2 — tập trung vào diễn giải ECG (diagnostic superclass, rhythm/AFIB), **chưa đề cập LVEF**.

Do đó, khoảng trống lớn nhất không chỉ là khoảng trống học thuật (framework nào tốt hơn để dự đoán LVEF từ ECG — vấn đề này đã có nhiều tiền lệ trong y văn) mà là **khoảng trống dữ liệu**: project cần một bộ dữ liệu ECG ghép cặp với nhãn LVEF trước khi có thể huấn luyện hoặc benchmark bất kỳ mô hình nào.

## 5. Mục tiêu nghiên cứu

Mục tiêu tổng quát: xây dựng và đánh giá một pipeline end-to-end — từ thu thập/ghép nối dữ liệu ECG–LVEF đến huấn luyện mô hình — để ước lượng LVEF và sàng lọc LVEF thấp (HFrEF) từ ECG 12 chuyển đạo.

Các mục tiêu cụ thể:

1. Xác định và thẩm định (validate) ít nhất một nguồn dữ liệu công khai có thể ghép cặp ECG với nhãn LVEF (ưu tiên MIMIC-IV-ECG + MIMIC-IV Echo/Notes).
2. Xây dựng pipeline trích xuất LVEF từ báo cáo siêu âm tim dạng free-text (NLP/regex) và quy tắc ghép ECG với lần đo LVEF gần nhất về thời gian.
3. Thống kê chất lượng nhãn (coverage, độ trễ thời gian ECG–echo, phân bố LVEF) và loại trừ các cặp ghép không đáng tin cậy.
4. Xây dựng một mô hình phân loại nhị phân duy nhất trả lời câu hỏi "LVEF ≤ 40%?", tái sử dụng backbone/pretrained weights từ VinStroke-ECG khi khả thi (transfer learning từ PTB-XL).
5. Đánh giá mô hình bằng các metric sàng lọc (AUROC, AUPRC, sensitivity/specificity tại ngưỡng lâm sàng, đối chứng trực tiếp với mốc AUC ≈ 0.93 của Attia et al. 2019).
6. Phân tích calibration và explainability cho nhánh phân loại sàng lọc LVEF thấp.
7. Đánh giá khả năng tổng quát hóa khi áp dụng mô hình huấn luyện trên dữ liệu nước ngoài (MIMIC — dân số ICU/Mỹ) sang bối cảnh Việt Nam, và đề xuất lộ trình thu thập dữ liệu nội bộ (ECG ghép với báo cáo siêu âm tim từ bệnh viện đối tác) cho external validation.

## 6. Câu hỏi nghiên cứu

**RQ1.** Có thể xây dựng một bộ dữ liệu ECG–LVEF đủ lớn và đủ tin cậy từ nguồn công khai (MIMIC-IV-ECG + Echo notes) bằng NLP/regex extraction không, và chất lượng nhãn trích xuất được ra sao so với nhãn cấu trúc?

**RQ2.** Mô hình học từ CWT/STFT + 12-lead grid (kế thừa VinStroke-ECG) có dự đoán LVEF tốt hơn mô hình học trực tiếp từ raw ECG signal không?

**RQ3.** Transfer learning từ backbone đã pretrain trên PTB-XL (diagnostic classification) có cải thiện hiệu quả dự đoán LVEF so với huấn luyện từ đầu không?

**RQ4.** Mô hình phân loại nhị phân "LVEF ≤ 40%" đạt được sensitivity/specificity ở mức nào so với mốc tham chiếu trong y văn (Attia et al. 2019: AUC ≈ 0.93)?

**RQ5.** Mô hình huấn luyện trên dữ liệu MIMIC (dân số Mỹ) có generalize tốt sang một mẫu dữ liệu ECG–echo nội bộ (nếu thu thập được từ bệnh viện đối tác Việt Nam) không?

**RQ6.** Calibration và explainability (Grad-CAM, lead-wise importance) của mô hình sàng lọc LVEF thấp có đủ tin cậy để hỗ trợ diễn giải lâm sàng không?

## 7. Phát biểu bài toán

### 7.1. Input

```text
X = ECG 12 chuyển đạo (10 giây), cùng cấu trúc input như VinStroke-ECG:
    Raw ECG signal
    CWT scalogram
    STFT spectrogram
    12-lead image grid
```

### 7.2. Output

```text
Y = 1{LVEF <= 40%}, nhãn nhị phân duy nhất (threshold lâm sàng HFrEF phổ biến nhất)
```

### 7.3. Dạng bài toán

```text
Binary classification: 1 câu hỏi duy nhất, 1 head duy nhất (low-EF screening)
```

MVP chủ động **không** làm multi-task (bỏ nhánh hồi quy LVEF %) để: (a) tận dụng được cả các report chỉ mô tả định tính (không có số chính xác nhưng đủ để suy ra nhãn nhị phân), (b) đơn giản hóa đánh giá — so sánh trực tiếp bằng AUROC/AUPRC/sensitivity/specificity với mốc tham chiếu Attia et al. (2019), (c) dễ trình bày kết quả với đối tác lâm sàng/bệnh viện. Việc dự đoán giá trị LVEF liên tục (để theo dõi xu hướng) được để lại như hướng mở rộng sau khi MVP binary đã chứng minh hiệu quả (xem mục 16).

## 8. Dataset strategy — trọng tâm của đề tài

Vì đây là điểm nghẽn chính, dataset strategy được trình bày theo thứ tự ưu tiên thực thi, không theo vai trò "core/external" như VinStroke-ECG gốc.

### 8.1. Ưu tiên 1: MIMIC-IV-ECG ghép với MIMIC-IV Echo / Discharge/Radiology Notes

MIMIC-IV-ECG (PhysioNet) cung cấp ~800.000 bản ghi ECG 12 chuyển đạo của ~160.000 bệnh nhân tại BIDMC, có `subject_id` và `ecg_time` để ghép nối với các module khác của MIMIC-IV (bao gồm ghi chú lâm sàng chứa báo cáo siêu âm tim).

Quy trình đề xuất:

* Trích các báo cáo có chứa cụm từ liên quan LVEF/ejection fraction từ free-text notes (MIMIC-IV-Note) bằng regex (ví dụ `EF\s*(of|is|:)?\s*\d{1,2}\s*%`, `ejection fraction.{0,20}\d{1,2}\s*%`) kết hợp rule ánh xạ các cách viết định tính ("normal EF" → nhãn 0, "severely/moderately reduced EF" → nhãn 1) sang nhãn nhị phân trực tiếp — vì MVP chỉ cần biết bên nào của ngưỡng 40%, các report định tính này **vẫn dùng được** thay vì phải loại bỏ, giúp tăng đáng kể lượng dữ liệu khả dụng so với việc bắt buộc phải có số LVEF chính xác.
* Với mỗi ECG, ghép với giá trị LVEF gần nhất về thời gian trong một cửa sổ cho phép (ví dụ ± 7 hoặc ± 30 ngày); loại các cặp có khoảng cách thời gian quá lớn để giảm nhiễu do thay đổi lâm sàng giữa hai lần đo.
* Lấy mẫu ngẫu nhiên một tập nhỏ (ví dụ 100-200 cặp) để **thẩm định thủ công** độ chính xác của bước trích xuất trước khi dùng cho toàn bộ pipeline.

Yêu cầu tiên quyết: hoàn tất chứng nhận CITI "Data or Specimens Only Research" và ký Data Use Agreement trên PhysioNet để truy cập MIMIC-IV, MIMIC-IV-ECG và MIMIC-IV-Note (Clinical Notes) — đây cần được thực hiện ở Phase 0 trước khi bắt đầu.

### 8.2. Ưu tiên 2: UK Biobank imaging substudy (future, không bắt buộc cho MVP)

UK Biobank có phân nhóm hình ảnh với cả ECG (điện tâm đồ khi nghỉ) và MRI tim (LVEF đo bằng CMR, chính xác hơn echo). Đây là nguồn dữ liệu chất lượng cao nhưng đòi hỏi apply access, chi phí, và thời gian chờ duyệt dài — phù hợp làm external validation trong giai đoạn sau, không phải MVP.

### 8.3. Ưu tiên 3 (song song, dài hạn): Dữ liệu nội bộ — ứng viên chính là Vinmec

Vì mô hình huấn luyện trên MIMIC phản ánh dân số Mỹ (ICU, tuổi, bệnh nền, thiết bị đo khác biệt với Việt Nam), giá trị lâm sàng thực sự tại Việt Nam cần được kiểm chứng trên dữ liệu nội bộ. Đây là bước quan trọng nhất để đánh giá độ tin cậy triển khai thực tế tại Việt Nam, không phải bước tùy chọn.

**Vinmec** được chọn là ứng viên ưu tiên vì: (a) là hệ thống bệnh viện tư nhân lớn, có hạ tầng bệnh án điện tử (EMR) tương đối hiện đại; (b) làm ECG và siêu âm tim thường quy nên hai loại dữ liệu này chắc chắn tồn tại trong hệ thống, khả năng ghép được qua mã bệnh nhân + thời gian; (c) đã có tiền lệ làm AI y tế và public dataset ảnh y khoa (VinDr-CXR, VinDr-Mammo, VinDr-SpineXR qua VinBigData/VinBrain trước đây), nên năng lực kỹ thuật xử lý/ẩn danh hóa dữ liệu không phải rào cản.

**Trạng thái hiện tại:** chưa có xác nhận công khai rằng Vinmec có/sẵn sàng chia sẻ bộ dữ liệu ECG–siêu âm tim ghép cặp. Không tìm thấy dataset ECG/LVEF nào được Vinmec hoặc VinBigData công bố công khai (khác với các dataset ảnh X-quang/nhũ ảnh đã có). Đây là việc cần xác nhận trực tiếp, không thể suy ra từ tìm kiếm công khai.

**Kênh tiếp cận:** không hỏi bác sĩ điều trị đơn lẻ (họ không có thẩm quyền chia sẻ dữ liệu), mà đi qua hai hướng song song:
1. Phòng/Trung tâm Nghiên cứu khoa học của Vinmec — đầu mối chính thức cho hợp tác nghiên cứu, biết quy trình IRB.
2. Bác sĩ tim mạch quen biết tại Vinmec (nếu có) — dùng làm người giới thiệu nội bộ sang phòng nghiên cứu, không kỳ vọng họ tự quyết việc chia sẻ dữ liệu.

**Câu hỏi cần xác nhận trước khi lập kế hoạch chi tiết cho nhánh dữ liệu này:**
* ECG có được lưu số hóa hay chủ yếu bản giấy/PDF scan rời rạc?
* Kết quả siêu âm tim có nhập số LVEF (%) dạng có cấu trúc trong EMR, hay chỉ là báo cáo free-text?
* Có thể liên kết ECG và siêu âm tim của cùng bệnh nhân qua mã bệnh án nội bộ không?
* Ước lượng số bệnh nhân có cả hai loại dữ liệu trong vài năm gần đây (quyết định n khả dụng cho external test set)?
* Quy trình xin dữ liệu ẩn danh cho nghiên cứu (qua IRB) làm việc qua phòng ban nào, mất bao lâu?

Nếu Vinmec không khả thi (từ chối, dữ liệu không đủ số hóa, hoặc quy trình quá lâu so với timeline đề tài), phương án dự phòng là tìm bệnh viện đối tác khác trong hệ sinh thái project AIA/VN đang triển khai, giữ nguyên vai trò external test set như thiết kế ban đầu.

* Xin phê duyệt IRB/đạo đức cho việc trích xuất ghép ECG–báo cáo siêu âm tim đã ẩn danh.
* Xây một tập nhỏ (vài trăm đến vài nghìn cặp) làm **external test set**, không dùng để huấn luyện.

### 8.4. Không sử dụng làm nguồn nhãn LVEF

Toàn bộ dataset hiện có trong project (PTB-XL, Chapman, Georgia, CPSC2018, PTB, INCART, ACS_ECG nội bộ) **không có LVEF** và không nên chỉnh sửa/giả lập nhãn. Các dataset này vẫn hữu ích để: (a) pretrain backbone qua nhiệm vụ diagnostic classification (transfer learning), (b) kiểm tra domain shift giữa các nguồn ECG khác nhau, nhưng không đóng vai trò ground-truth cho LVEF.

## 9. Thiết kế phương pháp

### 9.1. Tổng quan

```text
Stage 1: ECG-LVEF Pairing & Label Extraction Layer  (bước mới, riêng cho đề tài này)
Stage 2: ECG Representation Layer                    (tái sử dụng VinStroke-ECG)
Stage 3: Backbone + Transfer Learning Layer          (tái sử dụng/pretrained từ PTB-XL)
Stage 4: Binary Screening Prediction Layer (1 head duy nhất: LVEF <= 40%?)
```

### 9.2. Stage 1: ECG–LVEF Pairing & Label Extraction

* NLP/regex extraction LVEF từ free-text notes.
* Time-window matching ECG ↔ echo report.
* Manual QC trên tập mẫu.
* Loại trừ nhiễu: nhiều LVEF trong cùng report (chọn giá trị được nhắc gần "impression"/"conclusion"), giá trị định tính không kèm số, giá trị ngoài khoảng sinh lý hợp lý (ví dụ < 5% hoặc > 85%).

### 9.3. Stage 2 & 3: Representation và Backbone

Tái sử dụng trực tiếp hạ tầng VinStroke-ECG:

```text
Raw ECG branch: 1D-ResNet, InceptionTime, TCN (đã có sẵn checkpoint trong project)
Vision branch: CWT/STFT 12-lead grid + ResNet18/ConvNeXtV2 (đã có sẵn checkpoint trên PTB-XL)
```

Chiến lược transfer learning: khởi tạo encoder từ trọng số đã huấn luyện trên PTB-XL (diagnostic superclass task), fine-tune trên tập ECG–LVEF, đóng băng (freeze) các layer đầu trong vài epoch đầu để tránh overfitting với tập LVEF thường nhỏ hơn PTB-XL.

### 9.4. Stage 4: Binary Screening Prediction Layer

```text
Head (Binary screening): dự đoán 1{LVEF <= 40%}, loss = BCE with logits
Class weight hoặc focal loss vì low-EF thường là minority class
```

Không có nhánh regression trong MVP (xem mục 7.3) — toàn bộ thiết kế, loss và evaluation chỉ xoay quanh một head nhị phân duy nhất.

## 10. Xử lý class imbalance và nhiễu nhãn

* LVEF thấp (≤ 40%) thường là nhóm thiểu số trong dân số chung → cần weighted BCE hoặc focal loss, và có thể oversampling nhẹ nhóm LVEF thấp cho batch sampling.
* Nhãn trích xuất bằng NLP có nhiễu vốn có (label noise) → cần báo cáo riêng độ tin cậy nhãn (qua manual QC) và cân nhắc loss có robustness với label noise (ví dụ label smoothing nhẹ).
* Một bệnh nhân có thể có nhiều ECG/echo → cần split theo `patient_id`/`subject_id` (không theo record) để tránh data leakage giữa train/val/test.

## 11. Thiết kế thực nghiệm

### Experiment 1: Label extraction validation
So sánh LVEF trích xuất tự động với nhãn thẩm định thủ công trên tập mẫu (agreement, mean absolute error của bước trích xuất).

### Experiment 2: Raw ECG baseline
```text
1D-ResNet, InceptionTime, TCN trên raw ECG → low-EF binary classification
```

### Experiment 3: Vision-based (CWT/STFT grid) baseline
So sánh với Experiment 2 để trả lời RQ2.

### Experiment 4: Transfer learning ablation
```text
From scratch vs. pretrained-on-PTB-XL encoder (frozen vs. fine-tuned)
```

### Experiment 5: Threshold sensitivity
```text
So sánh performance khi định nghĩa low-EF ở ngưỡng 35% vs 40%, dùng cùng một tập dữ liệu và mô hình
```

### Experiment 6: Calibration
Brier score, Expected Calibration Error, reliability diagram trước/sau calibration.

### Experiment 7: Explainability
Grad-CAM / lead-wise importance cho các ca dự đoán LVEF thấp đúng và sai, đối chiếu với hiểu biết lâm sàng (QRS giãn rộng, trục lệch trái, sóng Q bệnh lý...).

### Experiment 8: External validation (nếu có dữ liệu nội bộ VN)
So sánh performance internal test (MIMIC) vs external test (Việt Nam), phân tích performance drop và domain shift.

## 12. Evaluation metrics

### Binary screening head (LVEF <= threshold) — metric duy nhất của MVP
```text
AUROC, AUPRC
Sensitivity, Specificity tại ngưỡng đã chọn
F1-score
Số ca low-EF bị bỏ sót (false negative) — quan trọng nhất về mặt lâm sàng
```

### Reliability
```text
Brier score
Expected Calibration Error
```

### Data quality
```text
Coverage: % ECG có LVEF ghép được
Độ trễ thời gian trung bình giữa ECG và echo
Agreement giữa nhãn tự động và nhãn thẩm định thủ công
```

## 13. Expected result package

* **Bảng 1:** Thống kê pairing (số ECG, số bệnh nhân, coverage, phân bố LVEF, độ trễ thời gian ECG–echo).
* **Bảng 2:** Kết quả binary screening (AUROC/AUPRC/sensitivity/specificity) theo từng backbone (raw ECG vs CWT/STFT vision).
* **Bảng 3:** Kết quả binary screening theo từng ngưỡng LVEF (35% và 40%) — Experiment 5.
* **Bảng 4:** Ablation transfer learning (from scratch vs pretrained).
* **Bảng 5:** Calibration trước/sau.
* **Bảng 6:** Internal (MIMIC) vs external (VN) nếu có.
* **Hình 1:** Pipeline tổng thể (ECG–LVEF pairing → representation → backbone → binary screening head → evaluation).
* **Hình 2:** Grad-CAM cho các ca low-EF.

## 14. Đóng góp khoa học dự kiến

1. Một pipeline có thể tái sử dụng để ghép nối ECG với nhãn LVEF từ dữ liệu lâm sàng dạng free-text, kèm quy trình QC thẩm định độ tin cậy nhãn.
2. Đánh giá thực nghiệm việc tái sử dụng (transfer learning) backbone đã huấn luyện cho bài toán diagnostic classification (VinStroke-ECG/PTB-XL) sang bài toán sàng lọc LVEF.
3. Một mô hình sàng lọc nhị phân LVEF ≤ 40% (không phải hồi quy), đánh giá đầy đủ bằng cả performance, calibration và explainability — dễ đối chứng trực tiếp với mốc tham chiếu trong y văn.
4. Bước đầu đánh giá domain shift khi áp dụng mô hình từ dữ liệu quốc tế (MIMIC) sang bối cảnh Việt Nam, làm cơ sở cho việc thu thập dữ liệu nội bộ về sau.

## 15. Giá trị cộng đồng và ý nghĩa ứng dụng

Một công cụ sàng lọc LVEF thấp chỉ dựa trên ECG — vốn đã phổ biến ở hầu hết cơ sở y tế kể cả tuyến cơ sở — có thể giúp phát hiện sớm các trường hợp nghi ngờ suy tim/giảm chức năng thất trái mà chưa được chỉ định siêu âm tim, từ đó ưu tiên chuyển tuyến hoặc chỉ định siêu âm tim kịp thời. Đây không phải công cụ thay thế chẩn đoán bằng siêu âm tim, mà là công cụ hỗ trợ sàng lọc/ưu tiên, đặc biệt có giá trị ở các khu vực thiếu bác sĩ tim mạch hoặc thiết bị siêu âm.

## 16. Rủi ro và giới hạn

### Chất lượng nhãn trích xuất bằng NLP
Nhãn LVEF lấy từ free-text report có thể sai lệch do lỗi trích xuất, báo cáo nhắc nhiều giá trị LVEF (theo dõi qua thời gian), hoặc mô tả định tính không kèm số. Cần QC thủ công nghiêm ngặt trước khi kết luận.

### Data leakage
Một bệnh nhân có nhiều ECG và nhiều lần đo echo — bắt buộc split theo bệnh nhân, không theo bản ghi, để tránh leakage giữa train/val/test.

### Domain gap giữa MIMIC và Việt Nam
Dân số MIMIC (ICU tại Mỹ) khác biệt đáng kể với dân số mục tiêu tại Việt Nam về tuổi, bệnh nền, thiết bị đo ECG. Kết quả trên MIMIC không thể coi là bằng chứng hiệu quả lâm sàng tại Việt Nam nếu chưa có external validation.

### Yêu cầu pháp lý/đạo đức
Truy cập MIMIC-IV cần CITI training và Data Use Agreement. Nếu mở rộng sang dữ liệu nội bộ Việt Nam, cần phê duyệt IRB/đạo đức và quy trình ẩn danh hóa dữ liệu bệnh nhân.

### Không thay thế chẩn đoán
Mô hình chỉ là công cụ sàng lọc hỗ trợ, không được overclaim là thay thế siêu âm tim hoặc chẩn đoán suy tim.

## 17. Roadmap thực hiện

### Phase 0: Data access và pháp lý
* Hoàn tất CITI training, ký Data Use Agreement để truy cập MIMIC-IV, MIMIC-IV-ECG, MIMIC-IV-Note trên PhysioNet.
* Liên hệ Vinmec (qua Phòng Nghiên cứu khoa học và/hoặc bác sĩ tim mạch quen biết) để xác nhận 5 câu hỏi ở mục 8.3 — kết quả quyết định Vinmec có khả thi làm external test set hay cần tìm bệnh viện đối tác khác.

### Phase 1: Label extraction & QC
* Xây regex/NLP pipeline trích LVEF từ notes.
* Ghép ECG với LVEF theo cửa sổ thời gian.
* Thẩm định thủ công tập mẫu, báo cáo độ tin cậy nhãn.

### Phase 2: Dataset construction
* Thống kê coverage, phân bố LVEF, split theo patient_id (train/val/test).
* Loại trừ cặp ghép không đáng tin cậy theo tiêu chí đã định.

### Phase 3: Baseline training
* Train raw ECG baseline (1D-ResNet/InceptionTime) cho binary screening head.

### Phase 4: Transfer learning từ VinStroke-ECG/PTB-XL
* Khởi tạo encoder từ checkpoint PTB-XL đã có trong project.
* So sánh from-scratch vs transfer learning.

### Phase 5: Model selection & threshold ablation
* So sánh ngưỡng 35% vs 40% (Experiment 5).
* Chọn kiến trúc/backbone tốt nhất.

### Phase 6: Calibration & explainability
* Tính Brier score, ECE, Grad-CAM cho head sàng lọc.

### Phase 7: External validation (nếu khả thi)
* Test trên tập dữ liệu nội bộ Việt Nam (nếu đã có phê duyệt và dữ liệu).

### Phase 8: Report writing
* Tổng hợp bảng/hình, viết limitation, chuẩn bị báo cáo/manuscript.

## 18. Kết luận

VinStroke-ECG-LVEF mở rộng framework VinStroke-ECG hiện có sang bài toán ước lượng LVEF/sàng lọc suy tim từ ECG 12 chuyển đạo — một hướng đã có tiền lệ mạnh trong y văn (Attia et al. 2019) nhưng **chưa có nền tảng dữ liệu nào trong project hiện tại**. Do đó, trọng tâm giai đoạn đầu của đề tài không phải là thiết kế kiến trúc mô hình (có thể tái sử dụng phần lớn hạ tầng VinStroke-ECG), mà là xây dựng và thẩm định một pipeline ghép nối ECG với nhãn LVEF đáng tin cậy, ưu tiên từ MIMIC-IV-ECG kết hợp MIMIC-IV Notes, với external validation trên dữ liệu Việt Nam là mục tiêu dài hạn quan trọng nhất để đảm bảo giá trị triển khai thực tế.
