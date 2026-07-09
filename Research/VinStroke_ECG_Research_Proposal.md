# VinStroke-ECG: Hierarchical Multi-Label 12-Lead ECG Interpretation Using Multi-Representation Time-Frequency Vision Models

## 1. Tóm tắt đề xuất nghiên cứu

VinStroke-ECG là một hướng nghiên cứu AI y tế tập trung vào diễn giải ECG 12 chuyển đạo bằng các mô hình học sâu hiện đại. Thay vì xây dựng một mô hình phân loại nhị phân đơn giản như `AFIB vs non-AFIB`, đề tài đề xuất một framework diễn giải ECG theo hướng **hierarchical multi-label classification**, cho phép mô hình nhận diện đồng thời nhiều nhóm bất thường tim mạch trên cùng một bản ghi ECG.

Điểm mới của đề tài nằm ở việc không chỉ xử lý ECG như tín hiệu 1D hoặc một ảnh thời gian–tần số đơn lẻ. Thay vào đó, nghiên cứu đề xuất kết hợp nhiều lớp thông tin: tín hiệu ECG thô, biểu diễn thời gian–tần số đa góc nhìn, cấu trúc không gian của 12 chuyển đạo, học phân cấp theo nhóm bệnh và một nhánh riêng cho các rhythm labels có liên quan đến nguy cơ đột quỵ, đặc biệt là **AFIB – atrial fibrillation**.

Mục tiêu của đề tài không phải là dự đoán đột quỵ trực tiếp. Mục tiêu là xây dựng một framework AI hỗ trợ diễn giải ECG chuyên sâu, có khả năng phát hiện các bất thường tim mạch tổng quát và các rối loạn nhịp có liên quan đến nguy cơ đột quỵ. Do đó, giá trị cộng đồng của đề tài nằm ở khả năng hỗ trợ sàng lọc sớm, tăng khả năng tiếp cận công cụ đọc ECG thông minh và tạo nền tảng có thể mở rộng cho các hệ thống y tế số trong tương lai.

## 2. Tên đề tài

### Tên tiếng Việt

**VinStroke-ECG: Diễn giải ECG 12 chuyển đạo đa nhãn bằng mô hình thị giác thời gian–tần số đa biểu diễn**

### Tên tiếng Anh

**VinStroke-ECG: Hierarchical Multi-Label 12-Lead ECG Interpretation Using Multi-Representation Time-Frequency Vision Models**

### Tên ngắn gọn

**VinStroke-ECG**

## 3. Bối cảnh và động cơ nghiên cứu

Đột quỵ có liên quan chặt chẽ đến nhiều yếu tố tim mạch, trong đó rung nhĩ là một trong những yếu tố nguy cơ quan trọng đối với đột quỵ thiếu máu não. Trong thực hành lâm sàng, ECG là một phương pháp đo không xâm lấn, chi phí thấp và được sử dụng rộng rãi để đánh giá hoạt động điện học của tim.

Nhiều mô hình AI-ECG hiện nay xử lý ECG như tín hiệu một chiều, ví dụ raw waveform input cho CNN, RNN, Transformer hoặc InceptionTime. Cách tiếp cận này có ưu điểm là giữ nguyên thông tin tín hiệu gốc, nhưng chưa tận dụng đầy đủ các thành tựu mạnh của computer vision. Một số hướng khác chuyển ECG thành ảnh spectrogram hoặc scalogram, nhưng thường chỉ sử dụng một dạng biểu diễn đơn lẻ và chưa khai thác đầy đủ cấu trúc 12 chuyển đạo.

ECG 12 chuyển đạo không chỉ chứa thông tin theo thời gian. Nó còn chứa thông tin về hình thái sóng, nhịp, tần số, quan hệ giữa các lead và phân bố bất thường theo vùng điện học của tim. Vì vậy, việc kết hợp nhiều biểu diễn thời gian–tần số và giữ cấu trúc không gian của 12 lead có thể giúp mô hình học được đặc trưng phong phú hơn so với cách xử lý ECG đơn lẻ.

Đề tài này đề xuất một framework kết hợp:

* ECG 12 chuyển đạo.
* Raw ECG signal branch.
* CWT scalogram.
* STFT spectrogram.
* 12-lead ECG image grid.
* Modern vision backbone.
* Hierarchical multi-label classification.
* Rhythm-specific branch cho AFIB và các rhythm labels liên quan đến nguy cơ đột quỵ.
* Calibration và explainability để tăng độ tin cậy trong bối cảnh AI y tế.

## 4. Khoảng trống nghiên cứu

Các hướng tiếp cận hiện có thường rơi vào một trong ba nhóm chính.

Thứ nhất, nhiều mô hình xử lý ECG như tín hiệu 1D. Hướng này giữ được waveform gốc nhưng chưa khai thác mạnh khả năng học pattern hình ảnh của các vision backbone hiện đại.

Thứ hai, một số nghiên cứu chuyển ECG thành ảnh thời gian–tần số, nhưng thường chỉ dùng một dạng biểu diễn như spectrogram hoặc scalogram. Cách này có thể chưa đủ để biểu diễn đa dạng các đặc trưng về nhịp, hình thái sóng, biến đổi tần số và thay đổi cục bộ theo thời gian.

Thứ ba, nhiều mô hình phân loại ECG theo hướng flat classification hoặc binary classification. Tuy nhiên, trong thực tế, một bản ghi ECG có thể có nhiều bất thường đồng thời, ví dụ `MI + CD`, `STTC + HYP` hoặc `AFIB + STTC`. Do đó, ECG interpretation phù hợp hơn với bài toán **multi-label** và **hierarchical classification**.

Từ các khoảng trống trên, đề tài đề xuất một framework mới có khả năng kết hợp nhiều biểu diễn ECG, giữ cấu trúc 12 chuyển đạo, học theo cấu trúc nhãn phân cấp và bổ sung nhánh riêng cho các bất thường nhịp liên quan đến nguy cơ đột quỵ.

## 5. Mục tiêu nghiên cứu

Mục tiêu tổng quát của đề tài là xây dựng và đánh giá một framework AI cho diễn giải ECG 12 chuyển đạo theo hướng hierarchical multi-label classification, sử dụng nhiều biểu diễn thời gian–tần số và mô hình thị giác hiện đại.

Các mục tiêu cụ thể gồm:

1. Xây dựng pipeline tiền xử lý ECG 12 chuyển đạo và chuyển đổi tín hiệu thành các biểu diễn CWT scalogram và STFT spectrogram.

2. Thiết kế cấu trúc 12-lead ECG grid nhằm giữ quan hệ không gian giữa các chuyển đạo.

3. Train và so sánh các baseline trên raw ECG, single-representation image và multi-representation image.

4. Đánh giá hiệu quả của các modern vision backbones như ConvNeXtV2 hoặc Swin Transformer V2 trong bài toán ECG multi-label classification.

5. Thiết kế hierarchical classification head để học đồng thời diagnostic superclass, subclass và selected statements.

6. Thiết kế rhythm-specific branch cho các rhythm labels liên quan đến nguy cơ đột quỵ, đặc biệt là AFIB.

7. Đánh giá mô hình bằng các metrics phù hợp với multi-label learning và class imbalance, bao gồm AUROC, AUPRC, F1, sensitivity, specificity, calibration và explainability.

## 6. Câu hỏi nghiên cứu

Đề tài tập trung trả lời các câu hỏi nghiên cứu sau:

**RQ1.** Việc kết hợp nhiều biểu diễn thời gian–tần số, cụ thể là CWT scalogram và STFT spectrogram, có cải thiện hiệu quả phân loại ECG so với raw ECG hoặc single-representation image không?

**RQ2.** Cấu trúc 12-lead ECG grid có giúp mô hình học tốt hơn so với cách xử lý từng lead độc lập hoặc gộp lead không có cấu trúc không gian không?

**RQ3.** Các modern vision backbone như ConvNeXtV2 hoặc Swin Transformer V2 có vượt các baseline truyền thống như 1D-ResNet, InceptionTime và ResNet trên ảnh ECG không?

**RQ4.** Hierarchical multi-label learning có cải thiện khả năng dự đoán diagnostic superclass, subclass và statements so với flat multi-label classification không?

**RQ5.** Rhythm-specific branch có cải thiện khả năng nhận diện AFIB và các rhythm labels liên quan đến nguy cơ đột quỵ không?

**RQ6.** Mô hình có đủ độ tin cậy về calibration và explainability để hỗ trợ diễn giải kết quả trong bối cảnh medical AI không?

## 7. Phát biểu bài toán

### 7.1. Input

Mỗi mẫu dữ liệu là một bản ghi ECG 12 chuyển đạo, thường dài 10 giây:

```text
X = [I, II, III, aVR, aVL, aVF, V1, V2, V3, V4, V5, V6]
```

Mỗi lead là một chuỗi tín hiệu theo thời gian. Từ tín hiệu gốc, pipeline tạo ra các biểu diễn bổ sung:

```text
Raw ECG signal
CWT scalogram
STFT spectrogram
12-lead CWT grid
12-lead STFT grid
Multi-representation ECG image
```

### 7.2. Output

Mô hình dự đoán nhiều nhãn cùng lúc:

```text
Y = {y1, y2, ..., yk}
```

Các nhãn có thể thuộc các nhóm:

* Diagnostic superclass.
* Diagnostic subclass.
* Diagnostic statements.
* Rhythm statements.
* Form statements.
* Signal quality/artifact nếu dataset hỗ trợ.

### 7.3. Dạng bài toán

Đây là bài toán:

```text
Hierarchical multi-label ECG classification
```

Không nên định nghĩa là single-label hoặc multiclass classification thuần, vì một ECG có thể có nhiều bất thường đồng thời.

Ví dụ:

```text
MI + CD
STTC + HYP
AFIB + STTC
NORM + minor rhythm variation
```

Trong giai đoạn đầu, đề tài tập trung vào 5 diagnostic superclass của PTB-XL:

```text
NORM: Normal ECG
MI: Myocardial Infarction
STTC: ST/T Change
CD: Conduction Disturbance
HYP: Hypertrophy
```

Sau đó mở rộng sang subclass, selected diagnostic statements và rhythm labels.

## 8. Dataset strategy

### 8.1. Dataset lõi: PTB-XL

PTB-XL được chọn làm dataset chính vì có ECG 12 chuyển đạo, độ dài bản ghi chuẩn, nhãn chuyên gia, cấu trúc nhãn rõ ràng và split benchmark được sử dụng rộng rãi.

Vai trò của PTB-XL trong đề tài:

* Dataset chính để train, validation và test.
* Dùng 10-fold split được khuyến nghị, đặc biệt fold 10 cho internal test.
* Dùng `scp_codes` để xây dựng mapping giữa diagnostic superclass, subclass, statements, rhythm và form labels.
* Dùng để đánh giá primary performance của framework.

### 8.2. External validation: PhysioNet/CinC Challenge 2020

CinC 2020 là dataset phù hợp cho external validation vì gồm nhiều nguồn ECG 12 chuyển đạo khác nhau. Dataset này giúp kiểm tra khả năng tổng quát hóa của mô hình khi chuyển từ PTB-XL sang dữ liệu khác domain.

Vai trò trong đề tài:

* Kiểm tra domain generalization.
* Phân tích domain shift.
* Đối chiếu performance trên các nguồn ECG khác nhau.
* Tăng độ tin cậy khoa học của kết quả.

### 8.3. Rhythm transfer validation: PhysioNet/CinC Challenge 2017

CinC 2017 là dataset ECG một chuyển đạo, phù hợp để đánh giá hướng transfer cho AFIB và rhythm classification.

Vai trò trong đề tài:

* Kiểm tra khả năng nhận diện AFIB/rhythm trên single-lead ECG.
* Mở rộng định hướng ứng dụng sang wearable, smartphone hoặc thiết bị đo ECG cá nhân.
* Không phải dataset core, mà là validation mở rộng nếu đủ thời gian.

### 8.4. Future datasets: MIMIC-IV-ECG và CODE-II-open

MIMIC-IV-ECG và CODE-II-open không nên đặt làm dataset bắt buộc trong MVP, vì yêu cầu access, preprocessing, label mapping và compute phức tạp hơn. Tuy nhiên, đây là các nguồn dữ liệu quan trọng cho future work.

Vai trò tiềm năng:

* Mở rộng sang ECG foundation model.
* Liên kết ECG với clinical reports hoặc EHR.
* Nghiên cứu risk prediction dài hạn nếu có outcome.
* Đánh giá khả năng scale của framework trên dataset lớn.

## 9. Thiết kế phương pháp

### 9.1. Tổng quan framework

VinStroke-ECG gồm ba tầng chính:

```text
Stage 1: ECG Representation Layer
Stage 2: Multi-Branch Feature Learning Layer
Stage 3: Hierarchical Multi-Label Prediction Layer
```

Framework này được thiết kế để tận dụng đồng thời tín hiệu gốc, thông tin thời gian–tần số và cấu trúc không gian của 12 chuyển đạo.

### 9.2. Stage 1: ECG Representation Layer

Từ raw ECG 12 chuyển đạo, hệ thống tạo ra các biểu diễn sau:

#### Raw ECG

Raw ECG giữ nguyên thông tin tín hiệu gốc, bao gồm hình thái sóng P, QRS complex, sóng T, khoảng RR, biến thiên nhịp và các đặc trưng điện học khác.

#### CWT Scalogram

CWT phù hợp với ECG vì ECG có nhiều thành phần ngắn và cục bộ. CWT giúp biểu diễn tốt các biến đổi theo thời gian và tần số, đặc biệt với các thành phần như P wave, QRS complex và T wave.

#### STFT Spectrogram

STFT là biểu diễn thời gian–tần số phổ biến, dễ triển khai và phù hợp làm baseline so sánh với CWT. STFT giúp mô hình quan sát sự thay đổi phổ tần theo thời gian.

#### 12-lead ECG grid

Mỗi lead được chuyển thành một ảnh CWT hoặc STFT. Sau đó, 12 ảnh được ghép thành một grid theo cấu trúc ECG 12 chuyển đạo:

```text
I    II   III
aVR  aVL  aVF
V1   V2   V3
V4   V5   V6
```

Cách này giúp mô hình giữ quan hệ không gian giữa các chuyển đạo, thay vì xem từng lead như các tín hiệu độc lập.

### 9.3. Stage 2: Multi-Branch Feature Learning Layer

Framework có thể triển khai theo hai mức.

#### Core model

Core model sử dụng vision branch trên 12-lead CWT/STFT grid.

Backbone đề xuất:

```text
ResNet18/ResNet50 as image baseline
ConvNeXtV2 or Swin Transformer V2 as main model
```

Input có thể gồm:

```text
CWT only
STFT only
CWT + STFT
```

#### Hybrid model extension

Hybrid model kết hợp raw ECG branch và vision branch:

```text
Raw ECG branch: 1D-ResNet or InceptionTime
Vision branch: ConvNeXtV2 or Swin Transformer V2
Fusion module: feature concatenation or cross-attention
Output: hierarchical multi-label predictions
```

Hybrid extension giúp giảm rủi ro phản biện rằng việc chuyển ECG sang ảnh có thể làm mất thông tin tín hiệu gốc.

### 9.4. Stage 3: Hierarchical Multi-Label Prediction Layer

Output layer được chia thành nhiều head:

#### Head A: Diagnostic Superclass Head

Dự đoán 5 diagnostic superclass:

```text
NORM, MI, STTC, CD, HYP
```

Đây là head core của đề tài.

#### Head B: Diagnostic Subclass/Statement Head

Dự đoán các subclass hoặc statements có đủ số lượng mẫu. Không nên train toàn bộ 71 statements ngay nếu nhiều nhãn quá hiếm. Cần thống kê label frequency trước, sau đó chọn các nhãn đủ sample.

#### Head C: Rhythm-Specific Head

Dự đoán AFIB và các rhythm abnormalities có liên quan đến nguy cơ đột quỵ.

Head này giúp đề tài giữ liên hệ với VinStroke nhưng không overclaim rằng mô hình dự đoán đột quỵ trực tiếp.

## 10. Loss function và xử lý class imbalance

ECG multi-label classification thường gặp class imbalance nghiêm trọng. Một số nhãn xuất hiện rất nhiều, trong khi các nhãn hiếm có số lượng mẫu thấp.

Loss function đề xuất:

```text
BCE with logits
Weighted BCE
Focal Loss
Asymmetric Loss
```

Chiến lược sử dụng:

* BCE with logits làm baseline.
* Weighted BCE để xử lý imbalance giữa các class.
* Focal Loss hoặc Asymmetric Loss để cải thiện performance trên long-tail labels.
* Threshold optimization riêng cho từng class.
* Calibration sau training để cải thiện độ tin cậy xác suất đầu ra.

Ngoài ra, cần phân tích riêng performance của các label hiếm thay vì chỉ báo cáo macro average.

## 11. Thiết kế thực nghiệm

Đề tài cần được thiết kế theo hướng ablation study để chứng minh giá trị của từng thành phần trong framework.

### Experiment 1: Raw ECG baseline

**Mục tiêu:** Thiết lập baseline từ tín hiệu ECG gốc.

**Model:**

```text
1D-ResNet
InceptionTime
```

**Output:**

```text
Macro AUROC
Macro AUPRC
Macro-F1
Per-class F1
```

### Experiment 2: Single-representation image baseline

**Mục tiêu:** Kiểm tra hiệu quả của từng biểu diễn ảnh riêng lẻ.

**Input:**

```text
CWT scalogram
STFT spectrogram
```

**Model:**

```text
ResNet18
ResNet50
```

**So sánh:**

```text
Raw ECG vs CWT vs STFT
```

### Experiment 3: Multi-representation input

**Mục tiêu:** Kiểm tra liệu CWT + STFT có tốt hơn single-representation không.

**Input:**

```text
CWT only
STFT only
CWT + STFT
```

**Model:**

```text
ResNet baseline
ConvNeXtV2 or Swin Transformer V2
```

**So sánh:**

```text
Single-representation vs multi-representation
```

### Experiment 4: Modern vision backbone

**Mục tiêu:** Đánh giá hiệu quả của modern vision backbone.

**Model comparison:**

```text
ResNet18/ResNet50
ConvNeXtV2
Swin Transformer V2
```

**Mục tiêu báo cáo:**

* Backbone nào cho performance tốt nhất.
* Backbone nào cân bằng tốt nhất giữa performance và compute cost.
* Vision backbone có vượt baseline raw ECG hay không.

### Experiment 5: 12-lead structure ablation

**Mục tiêu:** Chứng minh giá trị của việc giữ cấu trúc 12 chuyển đạo.

**So sánh:**

```text
Lead-independent processing
Flattened lead representation
12-lead ECG grid
```

**Giả thuyết:** 12-lead grid giúp mô hình học tốt hơn quan hệ giữa các chuyển đạo.

### Experiment 6: Hierarchical learning

**Mục tiêu:** Kiểm tra hiệu quả của hierarchical multi-label learning.

**So sánh:**

```text
Flat multi-label classification
Hierarchical multi-label classification
```

**Output:**

* Superclass performance.
* Subclass performance.
* Statement-level performance nếu đủ sample.

### Experiment 7: Rhythm-specific branch

**Mục tiêu:** Đánh giá nhánh riêng cho rhythm labels, đặc biệt là AFIB.

**So sánh:**

```text
Without rhythm-specific head
With rhythm-specific head
```

**Metrics riêng cho AFIB:**

```text
AFIB AUROC
AFIB AUPRC
AFIB sensitivity
AFIB specificity
AFIB F1
False negative analysis
```

### Experiment 8: Calibration

**Mục tiêu:** Đánh giá độ tin cậy xác suất đầu ra.

**Metrics:**

```text
Brier score
Expected Calibration Error
Reliability diagram
Confidence distribution
```

**So sánh:**

```text
Before calibration
After calibration
```

### Experiment 9: Explainability

**Mục tiêu:** Tăng khả năng diễn giải trong bối cảnh medical AI.

**Phương pháp:**

```text
Grad-CAM
Attention map
Lead-wise importance
Time-frequency region importance
```

**Output mong muốn:**

* Mô hình chú ý vào lead nào.
* Mô hình chú ý vào vùng thời gian–tần số nào.
* Kết quả explainability có hợp lý với bất thường ECG dự đoán hay không.

### Experiment 10: External validation

**Mục tiêu:** Kiểm tra khả năng tổng quát hóa ngoài PTB-XL.

**Dataset:**

```text
PhysioNet/CinC Challenge 2020
PhysioNet/CinC Challenge 2017 for AFIB/rhythm transfer if feasible
```

**Output:**

* Performance drop giữa internal test và external validation.
* Domain shift analysis.
* Discussion về khả năng triển khai thực tế.

## 12. Evaluation metrics

Vì đây là bài toán multi-label và class imbalance, accuracy không nên là metric chính.

### Primary metrics

```text
Macro AUROC
Macro AUPRC
Macro-F1
Per-class F1
```

### Secondary metrics

```text
Micro AUROC
Micro AUPRC
Precision
Recall/Sensitivity
Specificity
Confusion matrix for superclass-level prediction
```

### Rhythm-specific metrics

```text
AFIB AUROC
AFIB AUPRC
AFIB sensitivity
AFIB specificity
AFIB F1
AFIB false negative rate
```

### Reliability metrics

```text
Brier score
Expected Calibration Error
Calibration curve
Confidence distribution
```

### Explainability outputs

```text
Grad-CAM visualization
Attention heatmap
Lead-wise importance score
Time-frequency region importance
```

Với các nhãn hiếm, AUPRC và per-class F1 quan trọng hơn accuracy và có thể có ý nghĩa hơn AUROC.

## 13. Expected result package

Để proposal có thể tạo ra kết quả đủ viết báo cáo hoặc bài báo, nghiên cứu cần tạo ra các bảng và hình sau:

### Bảng 1: Dataset statistics

* Số lượng records.
* Số lượng patients.
* Tần suất từng superclass.
* Tần suất subclass/statements được chọn.
* Tần suất rhythm labels, đặc biệt AFIB.
* Tỷ lệ label imbalance.

### Bảng 2: Raw ECG baseline performance

So sánh:

```text
1D-ResNet
InceptionTime
```

Metrics:

```text
Macro AUROC
Macro AUPRC
Macro-F1
Per-class F1
```

### Bảng 3: Representation comparison

So sánh:

```text
Raw ECG
CWT
STFT
CWT + STFT
```

Mục tiêu là chứng minh multi-representation có giá trị hơn một biểu diễn đơn lẻ.

### Bảng 4: Backbone comparison

So sánh:

```text
ResNet18
ResNet50
ConvNeXtV2
Swin Transformer V2
```

### Bảng 5: Ablation study

So sánh:

```text
Without 12-lead grid vs with 12-lead grid
Flat multi-label vs hierarchical multi-label
Without rhythm head vs with rhythm head
Single-representation vs multi-representation
```

### Bảng 6: Rhythm/AFIB-specific result

Báo cáo riêng cho AFIB:

```text
AUROC
AUPRC
F1
Sensitivity
Specificity
False negative rate
```

### Bảng 7: Calibration result

So sánh trước và sau calibration:

```text
Brier score
Expected Calibration Error
```

### Bảng 8: External validation result

Nếu thực hiện được:

```text
Internal PTB-XL test
External CinC 2020 test
Performance drop
Domain shift discussion
```

### Hình 1: Overall system architecture

Thể hiện pipeline:

```text
Raw ECG 12-lead
→ CWT/STFT transformation
→ 12-lead grid construction
→ vision backbone
→ hierarchical multi-label heads
→ rhythm-specific head
→ evaluation/explainability
```

### Hình 2: ECG representation examples

Hiển thị cùng một ECG dưới các dạng:

```text
Raw ECG
CWT scalogram
STFT spectrogram
12-lead image grid
```

### Hình 3: Grad-CAM/attention visualization

Minh họa vùng mô hình chú ý khi dự đoán một số class như AFIB, MI hoặc STTC.

## 14. Đóng góp khoa học dự kiến

Đề tài kỳ vọng tạo ra các đóng góp chính sau:

1. Đề xuất một framework diễn giải ECG 12 chuyển đạo theo hướng hierarchical multi-label classification, phù hợp hơn với bản chất lâm sàng của ECG so với binary hoặc single-label classification.

2. Đề xuất cách kết hợp nhiều biểu diễn thời gian–tần số, bao gồm CWT scalogram và STFT spectrogram, nhằm giúp mô hình học được các đặc trưng bổ sung về nhịp, hình thái sóng và biến đổi tần số.

3. Đề xuất cấu trúc 12-lead ECG grid để giữ quan hệ không gian giữa các chuyển đạo khi đưa ECG vào mô hình thị giác.

4. So sánh có hệ thống giữa raw ECG models, single-representation vision models, multi-representation vision models và modern vision backbones.

5. Thiết kế rhythm-specific branch cho các rhythm labels liên quan đến nguy cơ đột quỵ, đặc biệt là AFIB, nhưng không overclaim direct stroke prediction.

6. Đánh giá mô hình không chỉ bằng predictive metrics mà còn bằng calibration, explainability và external validation.

7. Tạo ra một hướng tiếp cận có giá trị cộng đồng, có thể hỗ trợ sàng lọc sớm bất thường tim mạch và mở rộng cho hệ thống y tế số trong tương lai.

## 15. Giá trị cộng đồng và ý nghĩa ứng dụng

Đề tài có ý nghĩa cộng đồng vì ECG là một xét nghiệm phổ biến, chi phí thấp và có thể triển khai rộng rãi ở nhiều tuyến y tế. Nếu mô hình AI có khả năng hỗ trợ diễn giải ECG chính xác hơn, hệ thống có thể góp phần hỗ trợ sàng lọc sớm các bất thường tim mạch, đặc biệt ở những nơi thiếu bác sĩ chuyên khoa.

Với nhóm rhythm labels như AFIB, mô hình có thể hỗ trợ phát hiện các dấu hiệu liên quan đến nguy cơ đột quỵ. Điều này không thay thế bác sĩ và không phải chẩn đoán đột quỵ trực tiếp, nhưng có thể đóng vai trò như một công cụ hỗ trợ cảnh báo, ưu tiên kiểm tra và định hướng thăm khám tiếp theo.

Về dài hạn, framework này có thể được mở rộng cho:

* Hệ thống đọc ECG hỗ trợ bác sĩ.
* Ứng dụng sàng lọc tại tuyến cơ sở.
* Wearable ECG hoặc single-lead ECG.
* ECG foundation model.
* Risk prediction nếu có thêm EHR, outcome và follow-up data.

## 16. Rủi ro và giới hạn

### Không dự đoán đột quỵ trực tiếp

PTB-XL không có outcome đột quỵ. Do đó, mô hình không thể dự đoán trực tiếp nguy cơ đột quỵ hoặc xác suất xảy ra đột quỵ. Mô hình chỉ phát hiện các bất thường ECG và rhythm abnormalities có liên quan đến nguy cơ tim mạch.

### Class imbalance

Một số nhãn ECG có rất ít mẫu. Cần thống kê tần suất label trước khi train, chọn các label đủ sample và không overclaim với các nhãn quá hiếm.

### Domain shift

Mô hình train trên PTB-XL có thể giảm performance khi test trên dataset khác. External validation trên CinC 2020 hoặc dataset khác là cần thiết để đánh giá khả năng tổng quát hóa.

### Label mapping

Các dataset khác nhau có thể dùng hệ nhãn khác nhau như SCP-ECG hoặc SNOMED-CT. Việc mapping label cần được xử lý cẩn thận để tránh so sánh sai.

### Compute cost

CWT/STFT image generation, 12-lead grid và modern vision backbone có thể yêu cầu GPU mạnh và thời gian train dài. Cần bắt đầu từ baseline nhẹ trước khi mở rộng sang model lớn.

### Mất thông tin khi chuyển ECG thành ảnh

Việc chuyển ECG sang ảnh có thể làm mất một phần thông tin tín hiệu gốc. Đề tài xử lý rủi ro này bằng cách so sánh với raw ECG baseline và có thể mở rộng sang hybrid model.

## 17. Roadmap thực hiện

### Phase 1: Dataset analysis

* Tải PTB-XL.
* Phân tích `scp_codes`.
* Thống kê tần suất superclass, subclass, statements và rhythm labels.
* Xây mapping nhãn.
* Chọn nhóm label đủ sample để train.

### Phase 2: Preprocessing and representation generation

* Chuẩn hóa raw ECG.
* Generate CWT scalogram.
* Generate STFT spectrogram.
* Xây 12-lead CWT grid.
* Xây 12-lead STFT grid.
* Kiểm tra chất lượng ảnh đầu vào.

### Phase 3: Baseline training

* Train 1D-ResNet hoặc InceptionTime trên raw ECG.
* Train ResNet18/ResNet50 trên CWT/STFT.
* Báo cáo baseline metrics.

### Phase 4: Main model training

* Train ConvNeXtV2 hoặc Swin Transformer V2.
* So sánh CWT, STFT và CWT + STFT.
* So sánh single-representation và multi-representation.

### Phase 5: Hierarchical and rhythm-specific learning

* Thêm hierarchical classification head.
* Thêm rhythm-specific head cho AFIB và rhythm labels.
* So sánh flat vs hierarchical, with vs without rhythm head.

### Phase 6: Calibration and explainability

* Thực hiện calibration.
* Báo cáo Brier score và ECE.
* Tạo Grad-CAM, attention map hoặc lead-wise importance.

### Phase 7: External validation

* Test trên CinC 2020 nếu đủ điều kiện.
* Test rhythm/AFIB transfer trên CinC 2017 nếu phù hợp.
* Phân tích domain shift.

### Phase 8: Report and paper writing

* Tổng hợp bảng kết quả.
* Viết ablation analysis.
* Viết discussion về clinical relevance.
* Viết limitation và future work.
* Chuẩn bị báo cáo hoặc manuscript.

## 18. Kết luận

VinStroke-ECG được định vị là một framework diễn giải ECG 12 chuyển đạo theo hướng hierarchical multi-label classification, không phải một mô hình dự đoán đột quỵ trực tiếp. Điểm mới của đề tài nằm ở việc kết hợp nhiều biểu diễn thời gian–tần số, giữ cấu trúc không gian của 12 chuyển đạo, sử dụng modern vision backbone và bổ sung rhythm-specific branch cho các bất thường liên quan đến nguy cơ đột quỵ như AFIB.

Đề tài có giá trị nghiên cứu vì không chỉ train một mô hình phân loại ECG, mà thiết kế một framework có thể được kiểm chứng thông qua nhiều lớp thực nghiệm: raw ECG baseline, single-representation image, multi-representation image, 12-lead grid, hierarchical learning, rhythm-specific branch, calibration, explainability và external validation.

Nếu triển khai đầy đủ, proposal này có thể tạo ra bộ kết quả metrics đủ mạnh để viết báo cáo khoa học hoặc phát triển thành bài báo, đồng thời giữ được định hướng cộng đồng: hỗ trợ sàng lọc sớm bất thường tim mạch, tăng khả năng tiếp cận công cụ đọc ECG thông minh và mở rộng cho các hệ thống y tế số trong tương lai.
