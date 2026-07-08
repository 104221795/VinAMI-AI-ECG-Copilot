# SP_Stroke — Định vị lâm sàng & tích hợp

*Sàng lọc nguy cơ đột quỵ qua thiết bị đeo — cụm sản phẩm Edge AI VinSmartFuture*

## 1. Phạm vi và giới hạn

SP_Stroke là hệ thống **sàng lọc nguy cơ đột quỵ** dựa trên tín hiệu đa kênh thu qua thiết bị đeo — ECG/PPG (dùng chung nền tảng SP4), huyết áp liên tục, SpO2, HRV — kết hợp dữ liệu lâm sàng nhập qua ứng dụng (tiền sử bệnh, thuốc đang dùng, yếu tố nguy cơ). Mô hình XGBoost + DNN phát hiện rung nhĩ (AF), chỉ số HRV bất thường, và ước tính mức nguy cơ đột quỵ trong 30 ngày.

> **Phạm vi áp dụng:** SP_Stroke là công cụ sàng lọc, không phải công cụ chẩn đoán, và không dùng cho xử trí đột quỵ cấp (thuộc phạm vi hệ thống AI Code Stroke — sản phẩm riêng biệt trong danh mục). Đầu ra giới hạn ở ba mức nguy cơ (thấp / trung bình / cao) kèm khuyến nghị khám — không đưa kết luận bệnh danh.

## 2. Khoa đối tác và đối tượng áp dụng

**Đơn vị đối tác tiềm năng:**
- Trung tâm/Đơn vị Đột quỵ — đơn vị tiếp nhận khi mức nguy cơ cao cần khám chuyên sâu
- Khoa Tim mạch — rung nhĩ là yếu tố nguy cơ hàng đầu gây đột quỵ do huyết khối
- Khoa Khám sức khỏe / gói tầm soát — kênh tiếp cận sàng lọc dân số rộng
- Trung tâm Phục hồi chức năng sau đột quỵ — theo dõi nguy cơ tái phát

**Đầu ra lâm sàng:**
- Cảnh báo sớm theo mức nguy cơ, kèm khuyến nghị khám
- Kết nối Telestroke qua SP9 (giọng nói) hỗ trợ tư vấn từ xa khi có cảnh báo

**Mặt bệnh / nhóm đối tượng áp dụng:** cũng như các sản phẩm sàng lọc khác trong danh mục, hệ thống chưa gắn với một mã bệnh (ICD-10) cụ thể. Nhóm ưu tiên:
- Người có yếu tố nguy cơ đã biết: tăng huyết áp, đái tháo đường, rối loạn lipid máu, tiền sử gia đình [6]
- Rung nhĩ kịch phát (paroxysmal AF) chưa phát hiện — nhóm khó bắt được bằng ECG 12 chuyển đạo đo một lần tại phòng khám do cơn ngắt quãng

> Danh sách yếu tố nguy cơ trên trùng khớp với nội dung giáo dục sức khỏe chính chủ của Vinmec [6], củng cố cơ sở lâm sàng khi trình bày cho lãnh đạo — không chỉ dựa vào y văn quốc tế mà còn khớp với tài liệu nội bộ Vinmec đã công bố.

**Không áp dụng** cho bệnh nhân đột quỵ cấp đang trong cấp cứu.

**Thị trường mục tiêu:** người có yếu tố nguy cơ (B2C), bệnh viện có đơn vị đột quỵ (B2B), trung tâm phục hồi chức năng, bảo hiểm sức khỏe.

## 3. Lợi ích của hệ thống

**Về cơ sở khoa học — cần nêu rõ khi trình bày:** khác với các sản phẩm đã có công bố riêng (ví dụ sEMG với F1 = 95,12%), mô hình XGBoost + DNN của SP_Stroke hiện **chưa có kết quả kiểm chứng** trên dữ liệu thật — đây là thiết kế đề xuất, chưa qua huấn luyện/validate. Bằng chứng khái niệm hiện có đến từ y văn quốc tế, không phải kết quả riêng của hệ thống:

- Apple Heart Study (2019) tuyển 419.297 người tham gia; trong số người nhận cảnh báo nhịp bất thường, 34% được xác nhận rung nhĩ qua ECG patch, với giá trị tiên đoán dương 0,84 — bằng chứng khái niệm quy mô lớn cho việc phát hiện AF qua cảm biến quang học đeo tay.
- Một nghiên cứu ML gần đây trên dữ liệu PPG từ Apple Watch (Hiraoka et al., 2022) đạt AUC 0,94 (sensitivity 0,91, specificity 0,84) khi phát hiện rung nhĩ sau phẫu thuật tim — tiền lệ kỹ thuật gần hơn với hướng tiếp cận ML của SP_Stroke.

**Bối cảnh cạnh tranh — cần chủ động nêu:** công nghệ phát hiện rung nhĩ qua cảm biến quang học đeo tay đã có sản phẩm thương mại phổ biến (Apple Watch, AliveCor Kardia). SP_Stroke không phải công nghệ hoàn toàn mới về cảm biến; khác biệt nằm ở ba điểm:
1. Kết hợp AF + HRV + xu hướng huyết áp thành **một điểm nguy cơ đột quỵ tổng hợp**, thay vì chỉ cảnh báo AF đơn lẻ.
2. Tích hợp trực tiếp vào quy trình lâm sàng Vinmec qua Telestroke/SP9, khác với ứng dụng tiêu dùng độc lập không kết nối hệ thống y tế.
3. Kiến trúc 3 tầng (mục 4) cho phép tiếp cận cả nhóm chưa sở hữu smartwatch — phù hợp đặc thù thị trường Việt Nam, nơi tỷ lệ sở hữu thiết bị đeo còn thấp hơn thị trường Âu-Mỹ.

**Lợi ích định tính:**
- Theo dõi liên tục ngoài viện — bắt được biến cố mà một lần đo tại phòng khám dễ bỏ sót
- Tăng khả năng phát hiện rung nhĩ kịch phát
- Mở rộng kênh tiếp cận sàng lọc dân số, tiềm năng hợp tác bảo hiểm sức khỏe
- Dùng chung nền tảng phần cứng/phần mềm với SP4 — tối ưu chi phí phát triển trong cụm 5 sản phẩm thiết bị đeo (SP1, SP3, SP4, SP_EEG, SP_Stroke)

**Tính năng bổ sung đề xuất — giáo dục nhận diện dấu hiệu cảnh báo:** khi điểm nguy cơ vượt ngưỡng trung bình/cao, app có thể kèm theo nội dung giáo dục ngắn về dấu hiệu đột quỵ cấp (méo miệng, yếu liệt một bên, nói ngọng, mất thăng bằng, đau đầu dữ dội đột ngột) dựa trên nội dung y khoa phổ thông của Vinmec [6]. Đây không phải chức năng chẩn đoán — chỉ là lớp giáo dục giúp người dùng và người nhà phản ứng nhanh hơn nếu biến cố cấp xảy ra, việc mà SP_Stroke (công cụ sàng lọc dài hạn) không tự đảm nhiệm. Chi phí triển khai gần như bằng 0 (nội dung tĩnh, không cần huấn luyện mô hình), phù hợp bổ sung vào Tầng 1–3 mà không ảnh hưởng roadmap kỹ thuật.

## 4. Kiến trúc triển khai — 3 tầng Graceful Degradation

Khác với sEMG (tận dụng hạ tầng Motion Lab sẵn có), SP_Stroke **không có hạ tầng tương tự sẵn có tại Vinmec** — đây là hạng mục đầu tư gần như mới hoàn toàn về phần cứng. Kiến trúc được thiết kế theo 3 tầng để không phụ thuộc vào một loại thiết bị duy nhất và phù hợp với các mức sẵn sàng khác nhau của người dùng:

| Tầng | Thiết bị | Khả năng | Rào cản tiếp cận |
|---|---|---|---|
| **Tầng 1** | Chỉ smartphone | Camera đo PPG định kỳ | Gần như bằng 0 |
| **Tầng 2** | Smartphone + smartwatch BYOD | Theo dõi liên tục 24/7 qua HealthKit/Health Connect | Cần sở hữu smartwatch |
| **Tầng 3** | Thiết bị chuyên dụng VinSmartFuture | Độ chính xác đạt chuẩn lâm sàng | Mô hình B2B qua bệnh viện |

**Khi người dùng không có smartwatch — vận hành Tầng 1:** dùng camera + đèn flash điện thoại, người dùng đặt đầu ngón tay lên camera để đo PPG (kỹ thuật đã phổ biến trên thị trường); đo **định kỳ theo lời nhắc** (ví dụ 2–3 lần/ngày) thay vì liên tục.

**Đánh đổi cần nêu thẳng:** đo định kỳ (spot-check) dễ bỏ sót đúng loại biến cố hệ thống muốn bắt — rung nhĩ kịch phát xảy ra ngoài thời điểm đo. Đây là giới hạn cố hữu của Tầng 1, không phải lỗ hổng thiết kế. Để bù đắp: (1) điểm nguy cơ kết hợp cả yếu tố lâm sàng đã nhập qua app (tiền sử, thuốc, tuổi), không chỉ dựa vào tín hiệu đo được — nên Tầng 1 vẫn có giá trị sàng lọc dựa trên hồ sơ nguy cơ nền; (2) nếu điểm nguy cơ nền cao, hệ thống khuyến nghị đo thường xuyên hơn hoặc nâng cấp lên Tầng 2/3 để tăng độ nhạy phát hiện.

Kiến trúc này dùng chung nền tảng với SP4, giúp tối ưu chi phí phát triển trong tổng thể cụm sản phẩm.

## 5. Khả năng áp dụng trên hạ tầng vận hành (OH, eForm, EMR)

| Hạ tầng | Hiện trạng | Kế hoạch tích hợp |
|---|---|---|
| **OH (order/chỉ định)** | Chưa có mã chỉ định cho "sàng lọc nguy cơ đột quỵ qua thiết bị đeo" | Khởi tạo mã mới nếu đưa vào gói tầm soát sức khỏe định kỳ |
| **eForm** | Đã có trong thiết kế kiến trúc (nhập tiền sử bệnh, yếu tố nguy cơ qua app), nhưng nội dung form là **mới hoàn toàn** | Xây form mới — khác với sEMG, không tận dụng được form sẵn có |
| **EMR/HIS** | Dùng chung kiến trúc FHIR/HL7 đã định hình cho cụm thiết bị đeo | Cảnh báo đi qua kênh lâm sàng nội bộ trước khi tới người bệnh |
| **Telehealth** | **Đã xác nhận — Vinmec có hạ tầng Telemedicine nội bộ** kết nối phòng mổ/Cathlab/ICU giữa các bệnh viện trong hệ thống và chuyên gia trong/ngoài nước, vận hành theo mô hình hub-spoke (ví dụ: Vinmec Hạ Long hội chẩn với Times City); đã phục vụ ca đột quỵ theo chuẩn ANGLES. Ngoài ra có Telehealth bệnh nhân qua MyVinmec từ 2020 | Tích hợp SP9/Telestroke vào kênh Telemedicine chuyên gia-chuyên gia sẵn có, thay vì xây mới |

**Đánh giá khả thi hạ tầng:** ngược với sEMG, phần lớn cấu phần vận hành của SP_Stroke là **net-new** ở OH và eForm — cần đầu tư mới ở quy trình order và nội dung form. Điểm tích cực: kênh Telestroke (SP9) **không cần xây từ đầu** — Vinmec đã có hạ tầng Telemedicine nội bộ có thể tích hợp trực tiếp (xem chi tiết ở bảng trên). Đây là điểm cần nêu rõ khi so sánh mức ưu tiên triển khai giữa các chương trong danh mục.

## 6. Luồng vận hành tóm tắt

1. Người dùng đăng ký & nhập yếu tố nguy cơ (tiền sử bệnh, thuốc, gia đình) qua app.
2. Đeo thiết bị theo tầng phù hợp (mục 4) — theo dõi liên tục ECG/PPG, huyết áp, SpO2, HRV.
3. Mô hình chấm điểm nguy cơ đột quỵ 30 ngày; phát hiện AF/HRV bất thường.
4. Nếu vượt ngưỡng: cảnh báo định tuyến tới kênh lâm sàng nội bộ trước — không hiển thị trực tiếp cho người dùng khi chưa qua xem xét chuyên môn.
5. Telestroke (SP9) hỗ trợ tư vấn từ xa nếu cần.
6. Khuyến nghị khám trực tiếp tại Trung tâm/Đơn vị Đột quỵ hoặc Khoa Tim mạch khi mức nguy cơ cao.

## 7. Nguồn dữ liệu huấn luyện & validate

**Huấn luyện ban đầu (PoC) — dữ liệu công khai**, theo đúng kế hoạch đã chốt cho SP4 (nền tảng ECG/PPG mà SP_Stroke dùng chung pipeline HRV/edge):

| Bộ dữ liệu | Nội dung | Vai trò |
|---|---|---|
| **MIT-BIH AFDB** | 25 bản ghi ECG dài hạn (~10h/bản, 250 Hz), chủ yếu rung nhĩ kịch phát | Huấn luyện/kiểm thử phát hiện AF |
| **MIT-BIH Arrhythmia DB (MITDB)** | 48 bản ghi nửa giờ, 47 đối tượng | Đối chứng nhịp bình thường/bất thường khác |
| **CPSC2018** | 6.877 bản ghi ECG 12 chuyển đạo, đa dạng loại rối loạn nhịp (AF chiếm ~17,8%) | Mở rộng đa dạng dân số/thiết bị, validate cross-dataset |

**Dữ liệu vận hành thực tế** (khi triển khai) — hai luồng riêng biệt: (1) tín hiệu liên tục từ cảm biến thiết bị đeo (ECG/PPG, ước lượng huyết áp, SpO2, HRV); (2) dữ liệu lâm sàng nền do người dùng tự nhập qua app (tiền sử bệnh, thuốc, yếu tố nguy cơ).

**Khoảng trống cần lấp:** cả ba bộ dữ liệu công khai trên đều thu từ dân số nước ngoài (Mỹ, Trung Quốc) — cần fine-tune và validate trên dữ liệu người Việt thật qua pilot lâm sàng (phối hợp Khoa Tim mạch/Đơn vị Đột quỵ) trước khi công bố bất kỳ số liệu hiệu năng nào tại Vinmec.

## 8. Rủi ro kỹ thuật cần giải quyết

Khác với sEMG (chỉ cần xác nhận cấu hình thiết bị sẵn có), SP_Stroke có một rủi ro kỹ thuật cốt lõi cần giải quyết trước khi cam kết độ chính xác:

- **Đo huyết áp liên tục không xâm lấn** (ước lượng qua PTT/PPG) hiện **chưa đạt chuẩn y tế được công nhận rộng rãi** ở phần lớn thiết bị tiêu dùng — cần nêu thẳng, không hứa độ chính xác lâm sàng chưa kiểm chứng.
- Cần xác định chuẩn đối chiếu (huyết áp cuff) để hiệu chuẩn định kỳ cho từng người dùng.
- Cần xác nhận ngưỡng sai số chấp nhận được về mặt lâm sàng trước khi đưa vào logic cảnh báo.
- Cần kế hoạch validate mô hình AF/nguy cơ trên dữ liệu thật trước khi công bố bất kỳ số liệu hiệu năng nào.

## 9. Cơ sở khoa học & tài liệu tham khảo

- Perez MV, Mahaffey KW, Hedlin H, et al.; Apple Heart Study Investigators. *Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation.* N Engl J Med. 2019;381:1909–1917. DOI: 10.1056/NEJMoa1901183.
- Hiraoka D, Inui T, Kawakami E, et al. *Diagnosis of Atrial Fibrillation Using Machine Learning With Wearable Devices After Cardiac Surgery: Algorithm Development Study.* JMIR, 2022. DOI: 10.2196/35396.
- Moody GB, Mark RG. *A new method for detecting atrial fibrillation using R-R intervals.* Computers in Cardiology. 1983;10:227–230. — nguồn gốc MIT-BIH AFDB.
- Moody GB, Mark RG. *The impact of the MIT-BIH Arrhythmia Database.* IEEE Eng Med Biol. 2001;20(3):45–50. — nguồn gốc MITDB.
- Liu F, Liu C, Zhao L, et al. *An Open Access Database for Evaluating the Algorithms of ECG Rhythm and Morphology Abnormality Detection.* J Med Imaging Health Inform. 2018;8(7):1368–1373. DOI: 10.1166/jmihi.2018.2442. — nguồn gốc CPSC2018.
- Goldberger AL, Amaral LAN, Glass L, et al. *PhysioBank, PhysioToolkit, and PhysioNet.* Circulation. 2000;101(23):e215–e220. — trích dẫn chuẩn khi dùng bất kỳ bộ dữ liệu nào từ PhysioNet.
- **Lưu ý:** các nguồn trên là bằng chứng/dữ liệu từ y văn và kho dữ liệu quốc tế, dùng để chứng minh tính khả thi khái niệm và huấn luyện ban đầu — **không phải kết quả kiểm chứng của SP_Stroke tại Vinmec**.

**Nguồn về hạ tầng Vinmec:**

- [3] Vinmec Times City International Hospital — xác nhận hệ thống Telemedicine kết nối phòng mổ/Cathlab/ICU, hỗ trợ hội chẩn nội bộ Hệ thống Y tế Vinmec và chuyên gia trong/ngoài nước. Nguồn: https://www.vinmec.com/eng/hospital/vinmec-times-city-international-hospital
- [4] Bệnh viện Đa khoa Vinmec Hạ Long — ví dụ vận hành thực tế mô hình hub-spoke, hội chẩn từ xa với các bệnh viện lớn trong hệ thống. Nguồn: https://www.vinmec.com/vie/co-so-y-te/benh-vien-da-khoa-quoc-te-vinmec-ha-long
- [5] Chuyên khoa Cấp cứu, Vinmec — xác nhận Telemedicine đồng bộ chất lượng điều trị hồi sức cấp cứu toàn hệ thống, đã xử lý ca đột quỵ theo chuẩn ANGLES. Nguồn: https://www.vinmec.com/vie/chuyen-khoa/cap-cuu
- [6] Vinmec. *Đột quỵ: Nguyên nhân, dấu hiệu nhận biết, cách phòng tránh.* Tư vấn chuyên môn: BSCKI. Nguyễn Hồng Phúc (Hồi sức cấp cứu, Vinmec Phú Quốc). Cập nhật 13-05-2026. Nguồn nội dung giáo dục sức khỏe chính chủ Vinmec cho yếu tố nguy cơ và dấu hiệu cảnh báo đột quỵ. Nguồn: https://www.vinmec.com/vie/bai-viet/dot-quy-nguyen-nhan-dau-hieu-nhan-biet-cach-phong-tranh-vi

**Pháp lý:** tuân thủ Luật Bảo vệ Dữ liệu Cá nhân 2025 (số 91/2025/QH15) và Nghị định 356/2025/NĐ-CP (hiệu lực 01/01/2026).
