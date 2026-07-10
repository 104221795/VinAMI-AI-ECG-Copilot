# VinStroke-ECG: CWT 12-Lead ConvNeXtV2 for Multi-Label ECG Diagnostic Superclass Interpretation on PTB-XL

**Báo cáo nghiên cứu hoàn thiện**  
**Phiên bản artifact:** 10/07/2026  
**Phạm vi:** research prototype cho AI-assisted ECG interpretation

> **Tuyên bố phạm vi.** VinStroke-ECG là hệ thống hỗ trợ diễn giải ECG trong môi trường nghiên cứu. Hệ thống dự đoán nhóm nhãn bất thường ECG ở mức diagnostic superclass của PTB-XL; không thay thế chẩn đoán của bác sĩ. Đây không phải là hệ thống chẩn đoán đột quỵ, không phải mô hình loại trừ AMI sớm, không phải công cụ kích hoạt cath lab và không phải sản phẩm đã sẵn sàng dùng lâm sàng.

## 1. Tóm tắt điều hành

VinStroke-ECG là một **research prototype** cho bài toán AI-assisted ECG interpretation trên ECG 12 chuyển đạo. Nghiên cứu sử dụng PTB-XL, một bộ dữ liệu ECG công khai có nhãn được cấu trúc theo hệ thống SCP, để xây dựng bài toán **multi-label diagnostic superclass classification** với năm nhãn: NORM, MI, STTC, CD và HYP. Thay vì ép mỗi bản ghi vào đúng một nhãn, mô hình cho phép nhiều nhãn cùng dương tính khi dữ liệu có các bất thường đồng xuất hiện.

Luồng chính của hệ thống là: đọc ECG 12 chuyển đạo ở 100 Hz trong 10 giây, tiền xử lý tín hiệu, chuyển từng chuyển đạo sang biểu diễn Continuous Wavelet Transform (CWT), ghép thành CWT 12-lead grid, rồi đưa ảnh vào ConvNeXtV2-Base đã pretrained. Mô hình được huấn luyện 25 epoch bằng BCEWithLogitsLoss có trọng số dương theo lớp và AdamW. Checkpoint cuối cùng không được chọn theo epoch cuối, mà theo validation macro AUPRC; checkpoint tốt nhất xuất hiện tại epoch 9.

Trên tập test nội bộ của PTB-XL, mô hình đạt macro AUROC 0,886, macro AUPRC 0,730, macro F1 0,669; micro AUROC 0,905, micro AUPRC 0,799 và micro F1 0,707. NORM là nhãn hoạt động tốt nhất. STTC và CD cho kết quả tốt, MI ở mức chấp nhận được đến khá, còn HYP là điểm nghẽn rõ rệt. HYP có F1 0,451, AUPRC 0,456 và ECE 0,144, cho thấy vừa khó phân biệt vừa kém ổn định hơn về calibration.

Điểm quan trọng ở đây là kết quả cho thấy tính khả thi của hướng CWT 12-lead grid kết hợp ConvNeXtV2-Base đối với dự đoán nhóm nhãn bất thường ECG. Tuy nhiên, kết quả nên được hiểu là bằng chứng thực nghiệm nội bộ trên PTB-XL, không phải bằng chứng đủ cho ứng dụng lâm sàng. Full ablation CWT so với STFT chưa được chạy; chưa có baseline raw ECG 1D và chưa có external validation. Vì vậy, báo cáo này trình bày kết quả một cách thận trọng, đồng thời chỉ rõ các bước cần thiết để phát triển nghiên cứu tiếp theo.

## 2. Bối cảnh nghiên cứu và phát biểu bài toán

ECG 12 chuyển đạo là công cụ quan trọng để quan sát hoạt động điện học của tim. Mỗi chuyển đạo thể hiện cùng một hoạt động sinh lý từ một góc nhìn khác nhau; do đó, một bất thường có thể biểu hiện khác nhau giữa các chuyển đạo. Bài toán tự động hỗ trợ diễn giải ECG vì thế không chỉ là nhận diện một dạng sóng trong một chuỗi tín hiệu, mà còn cần khai thác quan hệ giữa hình thái, thời gian, tần số và cấu trúc 12 chuyển đạo.

Trong nhiều tình huống, một ECG có thể mang nhiều nhóm bất thường đồng thời. Ví dụ, một bản ghi có thể chứa MI-related ECG pattern đi kèm conduction disturbance, hoặc thay đổi ST/T cùng dấu hiệu hypertrophy. Cách đặt bài toán một nhãn duy nhất sẽ làm mất phần giao nhau này. VinStroke-ECG vì vậy sử dụng sigmoid độc lập cho từng nhãn thay vì softmax, nghĩa là mỗi nhãn có một score riêng và được so sánh với threshold riêng.

Mục tiêu cụ thể của phiên bản hiện tại là dự đoán năm diagnostic superclasses của PTB-XL:

| Mã nhãn | Diễn giải trong báo cáo | Cách hiểu đúng |
|---|---|---|
| NORM | Nhóm ECG bình thường trong PTB-XL | Nhãn tham chiếu của dataset, không phải kết luận lâm sàng độc lập |
| MI | MI-related ECG diagnostic superclass / MI-related ECG pattern | Nhận diện pattern thuộc superclass MI của PTB-XL; không phải chẩn đoán nhồi máu cơ tim cấp |
| STTC | ST/T change | Nhóm thay đổi tái cực ST/T trong taxonomy của PTB-XL |
| CD | Conduction disturbance | Nhóm rối loạn dẫn truyền trong taxonomy của PTB-XL |
| HYP | Hypertrophy | Nhóm pattern phì đại theo nhãn PTB-XL |

Đóng góp thực nghiệm của nghiên cứu không nằm ở việc tuyên bố một cách tiếp cận hoàn toàn mới cho CWT hoặc ECG AI. Giá trị hợp lý hơn là sự kết hợp có hệ thống giữa CWT 12-lead grid, ConvNeXtV2-Base, multi-label evaluation, class-specific threshold, calibration và explainability-oriented artifact export.

## 3. Vì sao đây không phải chẩn đoán đột quỵ hoặc AMI rule-out

Tên VinStroke-ECG gợi đến bối cảnh tim mạch và nguy cơ đột quỵ, nhưng dataset và output hiện tại không cho phép diễn giải như một mô hình dự đoán đột quỵ. PTB-XL không cung cấp outcome đột quỵ, dữ liệu theo dõi dài hạn, hình ảnh CT/CTA, thang điểm thần kinh hay biến cố điều trị. Vì vậy, mô hình không dự đoán đột quỵ và không được dùng để suy luận nguy cơ đột quỵ của một cá nhân.

Tương tự, nhãn MI của PTB-XL phải được trình bày là **MI-related ECG pattern** hoặc MI-related ECG diagnostic superclass. Hệ thống không tích hợp triệu chứng, troponin, thời điểm khởi phát, chuỗi ECG tại khoa cấp cứu, chẩn đoán ACS ở mức người bệnh, kết cục chụp mạch hoặc cath lab outcome. Do đó, hệ thống không phải early AMI rule-out và không hỗ trợ kích hoạt cath lab.

AFIB có xuất hiện trong manifest và thống kê dữ liệu với 1.451 record dương tính, tương đương 6,77%. Tuy nhiên, AFIB không nằm trong năm output head của checkpoint hiện tại. Nó là hướng mở rộng về rhythm head trong tương lai, không phải kết quả được huấn luyện và đánh giá trong báo cáo này.

Điều này cho thấy cách định vị chính xác nhất là: **AI-assisted 12-lead ECG interpretation for multi-label cardiac abnormality detection, using CWT 12-lead grid representation and ConvNeXtV2-Base on PTB-XL.** Hệ thống hỗ trợ diễn giải ECG và dự đoán nhóm nhãn bất thường ECG trong phạm vi nghiên cứu; không thay thế chẩn đoán của bác sĩ.

## 4. Dataset và xây dựng nhãn

### 4.1. PTB-XL và tập dữ liệu dùng trong thí nghiệm

PTB-XL là dataset lõi của nghiên cứu. Metadata `scp_codes` được parse và ánh xạ về diagnostic superclass thông qua bảng SCP statements. Sau khi loại các record không có nhãn mục tiêu, manifest trainable có 21.430 record từ 18.637 bệnh nhân đã được ẩn danh. Dữ liệu dùng `records100`, tương ứng tần số lấy mẫu 100 Hz.

Split tuân theo `strat_fold` của PTB-XL: fold 1-8 cho train, fold 9 cho validation và fold 10 cho test. Việc giữ split theo benchmark quan trọng hơn random split vì hạn chế nguy cơ leakage giữa các bản ghi liên quan và giúp kết quả có thể đối chiếu với setup PTB-XL.

| Tập dữ liệu | Số record | Vai trò |
|---|---:|---|
| Train | 17.111 | Học tham số mô hình |
| Validation | 2.156 | Chọn checkpoint và tối ưu threshold |
| Test | 2.163 | Đánh giá cuối cùng, không dùng để chọn mô hình |
| Tổng | 21.430 | Các record có ít nhất một nhãn mục tiêu |

[Chèn Hình 1: `reports/split_distribution.png` - phân bố train/validation/test theo split PTB-XL.]

### 4.2. Phân bố nhãn và mất cân bằng lớp

NORM có 9.528 record, tương đương 44,46% số record; HYP chỉ có 2.655 record, tương đương 12,39%. Tỷ lệ mất cân bằng của HYP so với lớp nhiều nhất là khoảng 3,59. Mất cân bằng này giải thích vì sao accuracy không phải metric chính: một mô hình thiên về nhãn phổ biến vẫn có thể có accuracy tốt nhưng bỏ sót nhãn ít hơn.

| Nhãn | Số record dương tính | Tỷ lệ trong manifest | Tỷ lệ mất cân bằng so với NORM |
|---|---:|---:|---:|
| NORM | 9.528 | 44,46% | 1,00 |
| MI | 5.486 | 25,60% | 1,74 |
| STTC | 5.250 | 24,50% | 1,81 |
| CD | 4.907 | 22,90% | 1,94 |
| HYP | 2.655 | 12,39% | 3,59 |

[Chèn Hình 2: `reports/class_counts.png` - số lượng record theo diagnostic superclass.]

[Chèn Hình 3: `reports/label_cooccurrence_matrix.png` - ma trận đồng xuất hiện nhãn, minh họa bản chất multi-label.]

Điều này cho thấy multi-label classification là lựa chọn phù hợp. Một record có thể thuộc nhiều nhóm, vì vậy mỗi nhãn cần score và threshold riêng. Trong pipeline, các nhãn được tạo bằng cách duyệt SCP code của mỗi record, ánh xạ code có `diagnostic_class` hợp lệ về NORM, MI, STTC, CD hoặc HYP, rồi tạo vector nhị phân năm chiều.

## 5. Pipeline tiền xử lý ECG

Pipeline có thể tóm tắt theo chuỗi sau:

```text
Raw ECG 12-lead
  -> load metadata và label mapping
  -> pad/crop về 10 giây
  -> band-pass filtering và chuẩn hóa theo lead
  -> CWT/STFT theo từng lead
  -> ghép 12 lead thành ảnh grid
  -> image dataset và ConvNeXtV2 training
  -> checkpointing, test evaluation, calibration
  -> single-sample inference, Grad-CAM và artifact export
```

Mỗi record gồm 12 chuyển đạo: I, II, III, aVR, aVL, aVF, V1, V2, V3, V4, V5 và V6. Với tần số 100 Hz và thời lượng 10 giây, input chuẩn có 1.000 mẫu cho mỗi lead. Trong quá trình tạo representation, tín hiệu được band-pass khoảng 0,5-40 Hz để giảm baseline drift và nhiễu tần số cao; sau đó từng lead được chuẩn hóa về trung bình 0 và độ lệch chuẩn 1. Mục tiêu không phải tạo tín hiệu “đẹp” về mặt thị giác, mà tạo đầu vào ổn định hơn cho biến đổi thời gian-tần số.

[Chèn Hình 4: `reports/raw_12lead_MI_ecg8.png` - ví dụ raw ECG 12 chuyển đạo của một record có nhãn MI-related ECG pattern.]

[Chèn Hình 5: `reports/spatial_12lead_MI_ecg8.png` - bố cục không gian 12 lead của cùng record. Lưu ý: artifact này là waveform grid, không phải CWT input.]

Điểm quan trọng ở đây là raw waveform và ảnh CWT có vai trò khác nhau. Raw waveform là tín hiệu nguồn để kiểm tra hình thái; CWT là representation được model thị giác sử dụng. Trong demo UI và trong báo cáo, hai loại artifact này không được thay thế cho nhau.

## 6. Biểu diễn CWT 12-lead grid

ECG là tín hiệu có các đặc trưng thay đổi theo thời gian. QRS complex, biến đổi ST/T và biến thiên nhịp không nhất thiết phân bố đồng đều trong cả 10 giây. CWT chuyển mỗi lead thành scalogram biểu diễn cường độ theo thời gian và scale/tần số. Cấu hình artifact hiện tại sử dụng Morlet wavelet (`morl`) với các scale 1-32; dải tần quan sát được giới hạn bởi tần số Nyquist của dữ liệu 100 Hz.

Sau khi tạo CWT cho từng lead, 12 ảnh được đặt trong grid 4 x 3 theo thứ tự:

```text
I    II   III
aVR  aVL  aVF
V1   V2   V3
V4   V5   V6
```

Cách ghép này bảo toàn cấu trúc trình bày quen thuộc của ECG 12 chuyển đạo, đồng thời biến đầu vào thành một ảnh RGB có thể dùng cho vision backbone. Ảnh được resize về 224 x 224 tại giai đoạn đưa vào model. CWT không tạo thêm thông tin lâm sàng mới; nó chỉ chuyển thông tin tín hiệu sang một representation khác để mô hình có thể học các pattern thời gian-tần số.

[Chèn Hình 6: `reports/ecg1_cwt_lead_II.png` - CWT của lead II.]

[Chèn Hình 7: `reports/ecg1_stft_lead_II.png` - STFT của cùng lead, dùng để đối chiếu representation.]

[Chèn Hình 8: `reports/ecg1_cwt_grid.png` - CWT 12-lead grid, là dạng input chính của checkpoint.] 

STFT cũng được sinh trong pipeline với cửa sổ Hann, `nperseg=128` và `noverlap=96` theo config artifact. Tuy nhiên, STFT hiện là representation/ablation module. Bảng `ablation_results.csv` chỉ có một dòng CWT main model và ghi rõ ablation chưa chạy. Vì vậy không thể kết luận CWT tốt hơn STFT từ artifact hiện có.

## 7. Kiến trúc mô hình: ConvNeXtV2-Base

Theo `config.json` và checkpoint artifacts, mô hình chính là `convnextv2_base` với `pretrained=true`. ConvNeXtV2-Base nhận ảnh CWT 224 x 224 và thay classifier head bằng năm logits tương ứng NORM, MI, STTC, CD và HYP. Sau inference, sigmoid được áp dụng độc lập trên từng logit để tạo năm model score.

Việc dùng pretrained vision backbone có hai lý do. Thứ nhất, CWT grid là dữ liệu ảnh có pattern cục bộ và cấu trúc lặp, phù hợp để tận dụng khả năng trích xuất đặc trưng của ConvNeXtV2. Thứ hai, fine-tuning từ trọng số pretrained thường giúp quá trình học ổn định hơn khi ảnh ECG không lớn như các tập ảnh tự nhiên. Tuy nhiên, pretrained ở đây không biến mô hình thành ECG foundation model; ảnh CWT có domain khác ImageNet và cần được đánh giá nghiêm túc trên chính bài toán ECG.

Model có năm output độc lập. Vì thế NORM và nhãn bất thường không bị ép loại trừ lẫn nhau bởi softmax. Đây là điểm phù hợp với taxonomy multi-label, nhưng cũng tạo ra tình huống có thể xảy ra output xung đột. Trong giao diện nghiên cứu, các output được xếp theo ưu tiên review thay vì diễn giải như một chẩn đoán duy nhất.

## 8. Chiến lược huấn luyện và chọn checkpoint

Mô hình được train 25 epoch với batch size 16, AdamW, learning rate 1e-4 và weight decay 1e-4. Loss là BCEWithLogitsLoss có `pos_weight`, trong đó trọng số được tính từ tỷ lệ negative/positive ở training set. Ví dụ, HYP có `pos_weight` cao nhất, khoảng 7,067, nhằm tăng đóng góp của positive HYP trong loss.

| Thành phần | Cấu hình artifact |
|---|---|
| Backbone | ConvNeXtV2-Base |
| Pretrained | True |
| Input | CWT 12-lead RGB grid, 224 x 224 |
| Nhãn | NORM, MI, STTC, CD, HYP |
| Loss | BCEWithLogitsLoss với class `pos_weight` |
| Optimizer | AdamW |
| Learning rate | 1e-4 |
| Weight decay | 1e-4 |
| Batch size | 16 |
| Epoch tối đa | 25 |
| Tiêu chí chọn checkpoint | Validation macro AUPRC |

Macro AUPRC được chọn làm checkpoint criterion vì bài toán mất cân bằng và cần quan tâm tương đối đồng đều tới từng nhãn. Accuracy có thể bị chi phối bởi NORM hoặc negative labels, còn macro AUPRC đánh giá precision-recall của từng nhãn rồi lấy trung bình. Đây là lựa chọn phù hợp hơn khi mục tiêu là dự đoán nhóm nhãn bất thường ECG.

Best validation macro AUPRC đạt 0,7217 tại epoch 9. Train loss sau đó tiếp tục giảm từ 0,546 ở epoch 9 xuống 0,152 ở epoch 25, nhưng validation macro AUPRC không vượt mốc tốt nhất và dao động thấp hơn. Điều này cho thấy plateau kèm dấu hiệu overfitting nhẹ. Vì vậy, `best_model.pt`, không phải `last_model.pt`, là checkpoint đúng để báo cáo test và demo.

[Chèn Hình 9: `reports/training_loss_curve.png` - training loss qua 25 epoch.]

[Chèn Hình 10: `reports/validation_metrics_curve.png` - validation metrics, nhấn mạnh best epoch gần epoch 9.]

## 9. Chỉ số đánh giá và ý nghĩa

Accuracy không phải chỉ số ưu tiên vì mất cân bằng nhãn và vì phần lớn cặp label-record là negative. Báo cáo dùng nhiều chỉ số để mô tả các khía cạnh khác nhau của mô hình:

| Chỉ số | Ý nghĩa trong nghiên cứu |
|---|---|
| Macro AUROC | Khả năng xếp hạng positive cao hơn negative, trung bình đều trên năm nhãn |
| Macro AUPRC | Chất lượng precision-recall dưới mất cân bằng lớp; là tiêu chí chọn checkpoint |
| Macro F1 | Hiệu quả quyết định sau threshold, cân bằng precision và recall |
| Precision | Trong các dự đoán dương tính, tỷ lệ đúng; thấp có thể tạo false positive |
| Recall/Sensitivity | Khả năng bắt positive; cao nhưng precision thấp cần được diễn giải thận trọng |
| Specificity | Khả năng nhận diện negative đúng |
| Brier score | Sai số bình phương giữa score và nhãn quan sát được; thấp hơn tốt hơn |
| ECE | Mức lệch giữa confidence và tần suất đúng theo các bin; thấp hơn tốt hơn |

Macro AUROC 0,886 cho thấy khả năng phân biệt/xếp hạng positive-negative nhìn chung tốt. Macro AUPRC 0,730 có ý nghĩa hơn trong bối cảnh imbalance vì nó phản ánh trade-off precision-recall thay vì bị chi phối bởi true negative. Macro F1 0,669 cho thấy sau khi áp dụng threshold, hệ thống đã tạo được các quyết định đa nhãn ở mức khả quan nhưng vẫn còn dư địa cải thiện.

Macro recall 0,778 cao hơn macro precision 0,596. Mô hình vì vậy có khuynh hướng nhạy trong việc bắt positive hơn là chính xác tuyệt đối trong mọi dự đoán dương. Đây không tự động là tốt hay xấu: nó phụ thuộc vào intended use, nhưng trong nghiên cứu hiện tại nó cho thấy false positive vẫn là vấn đề cần kiểm soát.

## 10. Kết quả thực nghiệm

### 10.1. Diễn biến huấn luyện

Các epoch đầu cho thấy validation macro AUPRC cải thiện nhanh: 0,499 ở epoch 1, 0,685 ở epoch 5, 0,713 ở epoch 7 và đỉnh 0,722 ở epoch 9. Sau đó metric dao động quanh 0,68-0,72. Sự phân kỳ giữa train loss tiếp tục giảm và validation không tiếp tục cải thiện là lý do chọn best checkpoint sớm.

| Mốc epoch | Train loss | Validation macro AUPRC | Diễn giải |
|---:|---:|---:|---|
| 1 | 0,995 | 0,499 | Mô hình bắt đầu học representation |
| 5 | 0,663 | 0,685 | Cải thiện nhanh |
| 7 | 0,599 | 0,713 | Tiến gần vùng tốt nhất |
| 9 | 0,546 | 0,722 | Best checkpoint |
| 15 | 0,344 | 0,694 | Dấu hiệu overfitting rõ hơn |
| 25 | 0,152 | 0,698 | Loss thấp nhưng không cải thiện validation |

### 10.2. Hiệu năng tổng thể trên test

| Metric | Giá trị |
|---|---:|
| Macro AUROC | 0,886 |
| Macro AUPRC | 0,730 |
| Macro F1 | 0,669 |
| Macro precision | 0,596 |
| Macro recall | 0,778 |
| Micro AUROC | 0,905 |
| Micro AUPRC | 0,799 |
| Micro F1 | 0,707 |

Kết quả macro và micro cùng cao cho thấy model học được tín hiệu có giá trị trên năm nhãn. Chênh lệch theo hướng micro cao hơn macro là phù hợp với mất cân bằng: micro chịu ảnh hưởng lớn hơn từ nhãn có support cao. Vì vậy, không nên chỉ báo micro metrics; phân tích per-class là bắt buộc để hiểu những nhãn yếu.

### 10.3. Hiệu năng theo nhãn

| Nhãn | Support | AUROC | AUPRC | F1 | Precision | Recall | Specificity |
|---|---:|---:|---:|---:|---:|---:|---:|
| NORM | 964 | 0,932 | 0,906 | 0,841 | 0,777 | 0,916 | 0,788 |
| MI | 553 | 0,862 | 0,696 | 0,649 | 0,569 | 0,754 | 0,804 |
| STTC | 523 | 0,919 | 0,797 | 0,706 | 0,609 | 0,839 | 0,828 |
| CD | 498 | 0,895 | 0,793 | 0,702 | 0,680 | 0,725 | 0,898 |
| HYP | 263 | 0,824 | 0,456 | 0,451 | 0,344 | 0,654 | 0,827 |

NORM là nhãn mạnh nhất, với cả AUROC, AUPRC và F1 cao. STTC và CD cũng có kết quả tốt; CD có specificity cao nhất trong các nhãn bất thường. MI có AUROC 0,862 và F1 0,649, cho thấy mô hình nhận diện MI-related ECG pattern ở mức chấp nhận được đến khá trên split nội bộ. Cần nhắc lại rằng điều này không tương đương với chẩn đoán nhồi máu cơ tim cấp trên bệnh nhân thực tế.

HYP là bottleneck chính. Support test chỉ 263, thấp hơn các nhãn khác; AUPRC 0,456 và precision 0,344 cho thấy mô hình khó duy trì precision khi dự đoán HYP. Đây có thể là hệ quả đồng thời của class imbalance, sự đồng xuất hiện với nhãn khác, độ separability thấp hơn của pattern HYP trong CWT image và loss hiện tại chưa đủ chuyên biệt cho long-tail multi-label learning.

[Chèn Hình 11: `reports/per_class_auroc.png` - AUROC theo nhãn.]

[Chèn Hình 12: `reports/per_class_auprc.png` - AUPRC theo nhãn; HYP thấp nhất.]

[Chèn Hình 13: `reports/per_class_f1.png` - F1 theo nhãn.]

### 10.4. Calibration

Calibration trả lời câu hỏi liệu model score có tương ứng hợp lý với tần suất đúng quan sát được hay không. Model score không phải xác suất bệnh lâm sàng; calibration chỉ đánh giá mức nhất quán giữa confidence của mô hình và nhãn test trong setup này.

| Nhãn | Brier score | ECE | Support |
|---|---:|---:|---:|
| NORM | 0,111 | 0,067 | 964 |
| MI | 0,146 | 0,098 | 553 |
| STTC | 0,114 | 0,096 | 523 |
| CD | 0,106 | 0,073 | 498 |
| HYP | 0,130 | 0,144 | 263 |
| Macro | 0,121 | 0,095 | - |

NORM và CD có calibration tương đối tốt hơn trong bảng này. HYP có ECE cao nhất, phù hợp với quan sát rằng nhãn này yếu cả về AUPRC lẫn F1. Vì vậy, bất kỳ demo nào cũng cần hiển thị HYP là model score kèm bằng chứng đánh giá hạn chế, không được trình bày như certainty lâm sàng.

[Chèn Hình 14: `reports/calibration_curve_macro.png` - macro calibration curve.]

### 10.5. Inference đơn mẫu

Artifact inference sử dụng ECG ID 9 trong test split. Ground truth của sample là NORM dương tính, bốn nhãn còn lại âm tính. Model score NORM là 0,970, vượt threshold 0,55; MI 0,049, STTC 0,010, CD 0,041 và HYP 0,026 đều thấp hơn threshold tương ứng. Đây là một minh họa end-to-end tốt cho pipeline từ raw ECG đến CWT grid và bảng xác suất.

| Nhãn | Ground truth | Model score | Threshold | Quyết định artifact |
|---|---:|---:|---:|---|
| NORM | 1 | 0,970 | 0,55 | Dương tính theo threshold |
| MI | 0 | 0,049 | 0,60 | Dưới threshold |
| STTC | 0 | 0,010 | 0,50 | Dưới threshold |
| CD | 0 | 0,041 | 0,65 | Dưới threshold |
| HYP | 0 | 0,026 | 0,50 | Dưới threshold |

[Chèn Hình 15: `reports/inference_raw_ecg_9.png` - raw ECG của sample inference.]

[Chèn Hình 16: `reports/inference_cwt_grid_9.png` - CWT grid được dùng cho inference.]

[Chèn Hình 17: `reports/inference_probabilities_9.png` - biểu đồ xác suất năm nhãn.]

Ví dụ này chỉ minh họa luồng kỹ thuật trên một record có ground truth đã biết. Nó không thể được dùng để suy rộng thành hiệu năng trên từng bệnh nhân hoặc thành bằng chứng chẩn đoán.

### 10.6. Grad-CAM explainability

Artifact set hiện có chứa các ảnh Grad-CAM-style cho NORM, MI, STTC và CD, ví dụ `explainability_ecg63_MI.png`. Utility Grad-CAM hiện tại sử dụng target layer phù hợp với timm ConvNeXtV2 (`model.stages[-1].blocks[-1].conv_dw`, với fallback là Conv2d cuối cùng). Điều này khắc phục giới hạn target-layer từng được ghi nhận trong bản notebook/report trước đó.

[Chèn Hình 18: `reports/explainability_ecg63_MI.png` - Grad-CAM-style overlay cho MI-related ECG pattern.]

Tuy nhiên, cần diễn giải rất thận trọng. Heatmap cho biết vùng CWT grid có ảnh hưởng tương đối đến score của model ở layer được chọn. Nó không chứng minh vị trí giải phẫu, không chứng minh quan hệ nhân quả và không thay thế việc đọc waveform. Trong ConvNeXtV2, attention map ở layer sâu có độ phân giải thấp trước khi nội suy, vì vậy ảnh overlay chủ yếu hữu ích để kiểm tra hành vi mô hình trong research prototype.

### 10.7. Trạng thái ablation

| Representation | Macro AUPRC | Macro AUROC | Macro F1 | Trạng thái |
|---|---:|---:|---:|---|
| CWT | 0,730 | 0,886 | 0,669 | Kết quả main model |

`ablation_results.csv` chỉ có một dòng CWT và ghi rõ full ablation chưa được chạy. STFT đã tồn tại trong pipeline như representation/ablation module, nhưng không có hàng STFT với cùng split, cùng epoch và cùng backbone để so sánh công bằng. Vì vậy, nghiên cứu không tuyên bố CWT tốt hơn STFT.

## 11. Thảo luận

Kết quả cho thấy ConvNeXtV2-Base có thể học representation hữu ích từ CWT 12-lead grid trên PTB-XL. Macro AUROC 0,886 biểu thị năng lực phân biệt tổng thể tốt, còn macro AUPRC 0,730 cho thấy hiệu quả vẫn có ý nghĩa khi đánh giá trong bối cảnh mất cân bằng. Việc NORM, STTC và CD có kết quả tốt cho thấy mô hình không chỉ học nhãn phổ biến NORM.

Tuy nhiên, cần diễn giải kết quả này một cách thận trọng. Macro F1 0,669 và macro precision 0,596 chỉ ra rằng thresholded outputs còn false positive đáng kể. Đây là lý do giao diện nghiên cứu nên xếp output theo ưu tiên review và hiển thị raw ECG/CWT cùng model score, thay vì trả về một “chẩn đoán”.

HYP là ví dụ rõ nhất về lý do không nên chỉ báo cáo một metric tổng. AUPRC thấp, F1 thấp và ECE cao cho thấy đây là nhãn khó cả ở phân biệt, quyết định threshold lẫn calibration. Từ góc nhìn nghiên cứu, HYP không phải chi tiết phụ mà là hướng cải tiến ưu tiên.

Một điểm tích cực khác là checkpoint selection. Việc chọn best model tại epoch 9 theo validation macro AUPRC có cơ sở rõ ràng hơn dùng epoch cuối. Điều này giảm rủi ro báo cáo kết quả của model đã overfit nhẹ ở cuối quá trình training.

## 12. Hạn chế

| Hạn chế | Tác động | Cách diễn giải đúng hiện tại |
|---|---|---|
| Không có outcome stroke | Không thể dự đoán đột quỵ | Chỉ nói hỗ trợ diễn giải ECG và phát hiện nhóm nhãn bất thường ECG |
| MI là superclass PTB-XL | Không phản ánh ACS workflow hoàn chỉnh | Dùng thuật ngữ MI-related ECG pattern, không gọi AMI rule-out |
| Chỉ internal test PTB-XL | Chưa biết khả năng tổng quát hóa domain khác | Không gọi clinical-ready hoặc robust across settings |
| Chưa có raw ECG baseline | Không biết CWT có hơn tín hiệu 1D hay không | Không tuyên bố superiority của representation |
| Ablation CWT/STFT chưa hoàn tất | Không có so sánh fair CWT-STFT | Không tuyên bố CWT tốt hơn STFT |
| HYP yếu | Dễ có false positive/score kém ổn định | Hiển thị bằng chứng per-class và review thận trọng |
| Grad-CAM là attention approximation | Không phải giải thích nhân quả | Chỉ dùng để kiểm tra hành vi model |
| Notebook gốc không có trong workspace hiện tại | Không thể audit từng cell từ file notebook | Mô tả pipeline được đối chiếu bằng config, report, code utilities và artifacts hiện có |

## 13. Hướng phát triển tiếp theo

1. Hoàn tất ablation công bằng CWT so với STFT: cùng ConvNeXtV2-Base, pretrained, split, augmentation, epoch budget và protocol chọn checkpoint.
2. Thêm baseline raw ECG 1D như 1D-ResNet hoặc InceptionTime để kiểm tra lợi ích thực sự của CWT image representation.
3. Cải thiện HYP bằng Focal Loss, Asymmetric Loss, class-balanced sampling, weighted sampler và threshold tuning riêng theo mục tiêu nghiên cứu.
4. Đánh giá calibration sau temperature scaling hoặc phương pháp calibration phù hợp, đặc biệt cho HYP.
5. Mở rộng external validation trên dataset ngoài PTB-XL sau khi xây dựng mapping nhãn minh bạch, ví dụ CinC 2020 hoặc MIMIC-IV-ECG nếu có quyền truy cập và protocol phù hợp.
6. Duy trì UI research demo theo luồng: CWT input -> five-label ranking -> raw waveform review -> Grad-CAM overlay -> export. UI phải giữ rõ distinction giữa raw waveform, CWT input và STFT research visual.
7. Phát triển rhythm/AFIB head như một bài toán riêng nếu có nhãn và đánh giá đầy đủ. Đây có thể là nền tảng cho nghiên cứu nguy cơ tim mạch sau này, nhưng không phải stroke diagnosis.
8. Nếu muốn nghiên cứu ACS/AMI triage trong tương lai, cần dữ liệu bổ sung như triệu chứng, troponin, timestamp, ED diagnosis và cath lab outcome. Những biến này không có trong thí nghiệm hiện tại.

## 14. Kết luận

VinStroke-ECG đã triển khai một pipeline có cấu trúc cho AI-assisted ECG interpretation: PTB-XL được ánh xạ về năm diagnostic superclasses, ECG 12 chuyển đạo được chuyển thành CWT grid, ConvNeXtV2-Base được fine-tune bằng multi-label objective, và kết quả được đánh giá bằng discrimination, thresholded metrics, calibration, inference artifact cùng Grad-CAM-style visualization.

Kết quả macro AUROC 0,886, macro AUPRC 0,730 và macro F1 0,669 cho thấy hướng CWT 12-lead ConvNeXtV2 có tính khả thi như research prototype. NORM mạnh nhất; STTC và CD tốt; MI đạt mức chấp nhận được đến khá trong phạm vi MI-related ECG pattern; HYP cần được cải thiện rõ rệt. Vì vậy, kết quả nên được dùng để định hướng nghiên cứu tiếp theo, không thay thế chẩn đoán của bác sĩ và không được trình bày như hệ thống dự đoán đột quỵ hay AMI rule-out.

## 15. Phụ lục: hướng dẫn đặt artifact

| Vị trí | Artifact đề xuất | Mục đích |
|---|---|---|
| Dataset split | `reports/split_distribution.png` | Minh họa train/validation/test |
| Class imbalance | `reports/class_counts.png` | Giải thích mất cân bằng và `pos_weight` |
| Multi-label | `reports/label_cooccurrence_matrix.png` | Minh họa nhãn đồng xuất hiện |
| Raw ECG example | `reports/raw_12lead_MI_ecg8.png` | Waveform nguồn của MI-related sample |
| Spatial waveform layout | `reports/spatial_12lead_MI_ecg8.png` | Bố cục 12 lead; không phải CWT |
| CWT/STFT lead | `reports/ecg1_cwt_lead_II.png`, `reports/ecg1_stft_lead_II.png` | So sánh time-frequency representation |
| CWT model input | `reports/ecg1_cwt_grid.png` hoặc `reports/inference_cwt_grid_9.png` | Đầu vào thực của vision checkpoint |
| Training dynamics | `reports/training_loss_curve.png`, `reports/validation_metrics_curve.png` | Best epoch và plateau |
| Per-class result | `reports/per_class_auroc.png`, `reports/per_class_auprc.png`, `reports/per_class_f1.png` | So sánh giữa năm nhãn |
| Calibration | `reports/calibration_curve_macro.png` | Diễn giải reliability của model score |
| Inference demo | `reports/inference_raw_ecg_9.png`, `reports/inference_cwt_grid_9.png`, `reports/inference_probabilities_9.png` | Luồng end-to-end một sample test |
| Explainability | `reports/explainability_ecg63_MI.png` | Minh họa Grad-CAM-style attention, không phải bằng chứng nhân quả |
| Ablation | `reports/ablation_results.csv` | Ghi rõ chỉ có main CWT row, ablation chưa hoàn tất |

### Nguồn tài liệu đã đối chiếu

- `Research/VinStroke_ECG_ConvNeXtV2_Report.docx` (bản report hiện tại).
- `Research/VinStroke_ECG_Research_Proposal.md` (đề xuất nghiên cứu).
- `VinStroke_ECG_artifacts/config.json`, manifests, reports, checkpoints và `VinStroke_ECG_Research_Report.md`.
- Các utility code hiện có trong `src/` cho manifest, CWT/STFT và Grad-CAM.

### Tài liệu tham khảo được kế thừa từ report hiện tại

1. Wagner, P., Strodthoff, N., Bousseljot, R.-D., et al. (2020). PTB-XL, a large publicly available electrocardiography dataset. *Scientific Data*. DOI: 10.1038/s41597-020-0495-6.
2. Strodthoff, N., Wagner, P., Schaeffter, T., & Samek, W. (2020). Deep Learning for ECG Analysis: Benchmarks and Insights from PTB-XL. arXiv:2004.13701.
3. Woo, S., Debnath, S., Hu, R., et al. (2023). ConvNeXt V2: Co-designing and Scaling ConvNets with Masked Autoencoders. arXiv:2301.00808.
4. Selvaraju, R. R., Cogswell, M., Das, A., et al. (2017). Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization. ICCV.
5. Ben-Baruch, E., Ridnik, T., Zamir, N., et al. (2020). Asymmetric Loss for Multi-Label Classification. arXiv:2009.14119.
