import { VinamiApiError } from "@vinami/api-client";

export interface ErrorPresentation {
  title: string;
  description: string;
  correlationId: string | null;
  retryable: boolean;
}

export function presentError(error: unknown): ErrorPresentation {
  if (!(error instanceof VinamiApiError)) {
    return {
      title: "Thông tin không khả dụng",
      description:
        "Không thể hoàn tất yêu cầu. Hãy thử lại hoặc liên hệ nhóm hỗ trợ nếu lỗi tiếp diễn.",
      correlationId: null,
      retryable: true,
    };
  }
  const messages: Record<typeof error.kind, [string, string]> = {
    authentication: [
      "Phiên làm việc không khả dụng",
      "Phiên xác thực bị thiếu hoặc đã hết hạn. Cần thiết lập lại phiên danh tính đã được phê duyệt.",
    ],
    authorization: [
      "Cần quyền truy cập",
      "Vai trò đã xác thực của bạn không cho phép xem thông tin lâm sàng này.",
    ],
    not_found: [
      "Không tìm thấy bản ghi",
      "Bản ghi có thể không còn trong quy trình đang hoạt động hoặc mã tham chiếu chưa đúng.",
    ],
    conflict: [
      "Dữ liệu ca đã thay đổi",
      "Backend đã có phiên bản mới hơn. Hãy làm mới trước khi tiếp tục để không ghi thao tác lên dữ liệu cũ.",
    ],
    validation: [
      "Yêu cầu không hợp lệ",
      "Kiểm tra bộ lọc hoặc dữ liệu đã chọn rồi thử lại với giá trị được hỗ trợ.",
    ],
    timeout: [
      "Dịch vụ phản hồi chậm",
      "Dịch vụ lâm sàng không phản hồi trong khoảng thời gian dự kiến.",
    ],
    offline: [
      "Không có kết nối",
      "Không thể kết nối tới dịch vụ lâm sàng. Hãy kiểm tra mạng trước khi dựa vào thông tin hiển thị.",
    ],
    server: [
      "Dịch vụ lâm sàng không khả dụng",
      "Máy chủ không thể hoàn tất yêu cầu. Không có thao tác lâm sàng nào được ghi nhận.",
    ],
    malformed: [
      "Phát hiện lệch hợp đồng dữ liệu",
      "Thông tin nhận được không vượt qua kiểm tra runtime nên chưa được hiển thị.",
    ],
    unknown: [
      "Yêu cầu chưa thành công",
      "Không thể hoàn tất yêu cầu một cách an toàn.",
    ],
  };
  const [title, description] = messages[error.kind];
  return {
    title,
    description,
    correlationId: error.correlationId,
    retryable: error.retryable,
  };
}
