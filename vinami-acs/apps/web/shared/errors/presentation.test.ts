import { describe, expect, it } from "vitest";
import { VinamiApiError } from "@vinami/api-client";
import { presentError } from "./presentation";

describe("error presentation", () => {
  it.each([
    ["authentication", "Phiên làm việc không khả dụng"],
    ["authorization", "Cần quyền truy cập"],
    ["not_found", "Không tìm thấy bản ghi"],
    ["conflict", "Dữ liệu ca đã thay đổi"],
    ["validation", "Yêu cầu không hợp lệ"],
    ["timeout", "Dịch vụ phản hồi chậm"],
    ["offline", "Không có kết nối"],
    ["server", "Dịch vụ lâm sàng không khả dụng"],
    ["malformed", "Phát hiện lệch hợp đồng dữ liệu"],
  ] as const)("maps %s distinctly", (kind, title) => {
    expect(
      presentError(new VinamiApiError(kind, "safe", 500, "corr", true)).title,
    ).toBe(title);
  });
});
