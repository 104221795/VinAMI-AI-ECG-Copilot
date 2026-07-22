import Link from "next/link";
import { EmptyState } from "@vinami/ui";

export default function NotFound() {
  return (
    <>
      <EmptyState
        title="Không tìm thấy trang"
        description="Không gian làm việc được yêu cầu chưa nằm trong phạm vi đang bật của hệ thống."
      />
      <p style={{ textAlign: "center" }}>
        <Link href="/command-center">Quay lại Trung tâm điều phối</Link>
      </p>
    </>
  );
}
