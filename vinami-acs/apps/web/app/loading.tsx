import { LoadingSkeleton } from "@vinami/ui";

export default function Loading() {
  return (
    <LoadingSkeleton
      lines={8}
      label="Đang tải thông tin quy trình lâm sàng đã xác thực"
    />
  );
}
