# Tóm tắt điều hành — SP_Stroke: Sàng lọc nguy cơ đột quỵ qua thiết bị đeo

## Tổng quan

Hệ thống AI **sàng lọc nguy cơ đột quỵ** dựa trên tín hiệu đa kênh từ thiết bị đeo (ECG/PPG dùng chung nền SP4, huyết áp liên tục, SpO2, HRV), kết hợp dữ liệu lâm sàng nhập qua ứng dụng (tiền sử bệnh, thuốc, yếu tố nguy cơ). Mô hình XGBoost + DNN phát hiện rung nhĩ (AF), HRV bất thường, và ước tính nguy cơ đột quỵ trong 30 ngày. Đầu ra là mức nguy cơ (thấp/trung bình/cao) kèm khuyến nghị khám.

**Giới hạn phạm vi:** công cụ sàng lọc, không phải chẩn đoán, không dùng cho xử trí đột quỵ cấp (thuộc hệ thống AI Code Stroke riêng biệt trong danh mục). Không thay thế đánh giá lâm sàng.

## Khoa đối tác

Trung tâm/Đơn vị Đột quỵ và Khoa Tim mạch (chủ đạo — rung nhĩ là yếu tố nguy cơ hàng đầu), Khoa Khám sức khỏe (kênh tầm soát dân số), Trung tâm Phục hồi chức năng (theo dõi tái phát). Đầu ra: cảnh báo sớm mức nguy cơ, kết nối Telestroke qua SP9.

## Định vị & khác biệt

**Không phải công nghệ cảm biến mới — khác biệt nằm ở tích hợp và khả năng tiếp cận.** Apple Watch và AliveCor đã thương mại hóa phát hiện rung nhĩ qua cảm biến quang học đeo tay. SP_Stroke khác ở ba điểm: (1) kết hợp AF + HRV + xu hướng huyết áp thành một điểm nguy cơ đột quỵ tổng hợp, thay vì chỉ cảnh báo AF đơn lẻ; (2) tích hợp trực tiếp vào quy trình lâm sàng Vinmec qua Telestroke, khác ứng dụng tiêu dùng độc lập; (3) kiến trúc 3 tầng (smartphone-only → BYOD smartwatch → thiết bị chuyên dụng) tiếp cận được cả nhóm chưa sở hữu smartwatch — phù hợp đặc thù thị trường Việt Nam.

## Ưu điểm và lợi ích

- **Theo dõi liên tục ngoài viện** — bắt được biến cố mà một lần đo tại phòng khám dễ bỏ sót
- **Tăng khả năng phát hiện rung nhĩ kịch phát** (paroxysmal AF)
- **Mở kênh sàng lọc dân số**, tiềm năng hợp tác bảo hiểm sức khỏe
- **Dùng chung nền tảng với SP4** — tối ưu chi phí phát triển trong cụm 5 sản phẩm thiết bị đeo
- **Bổ sung giáo dục dấu hiệu cảnh báo đột quỵ cấp** (dựa trên nội dung y khoa chính chủ Vinmec) khi điểm nguy cơ cao — chi phí triển khai gần như bằng 0

## Điểm cần quyết định trước triển khai

**Đo huyết áp liên tục không xâm lấn (ước lượng qua PTT/PPG) hiện chưa đạt chuẩn y tế được công nhận rộng rãi** — đây là rủi ro kỹ thuật cốt lõi, khác biệt so với các chương tận dụng hạ tầng sẵn có trong danh mục (vốn chỉ cần xác nhận cấu hình thiết bị). Hai việc cần làm trước khi cam kết độ chính xác:
- Xác định chuẩn đối chiếu (huyết áp cuff) để hiệu chuẩn định kỳ
- Xác nhận ngưỡng sai số chấp nhận được về mặt lâm sàng trước khi đưa vào logic cảnh báo

## Bước tiếp theo

1. Xác định chuẩn đối chiếu và kế hoạch hiệu chuẩn huyết áp liên tục.
2. Lên kế hoạch validate mô hình AF/nguy cơ trên dữ liệu thật trước khi công bố bất kỳ số liệu hiệu năng nào.
3. Xác nhận nền tảng telehealth hiện có tại Vinmec để tích hợp SP9/Telestroke.
4. Tuân thủ Luật Bảo vệ Dữ liệu Cá nhân 2025 (số 91/2025/QH15) và Nghị định 356/2025/NĐ-CP.
