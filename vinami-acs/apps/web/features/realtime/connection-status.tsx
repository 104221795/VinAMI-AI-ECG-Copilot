"use client";

import { formatTimestamp } from "@web/shared/formatting";
import type {
  RealtimeConnectionState,
  RealtimeNotificationView,
} from "./use-realtime-updates";

export function RealtimeStatus({
  state,
  lastUpdateAt,
  notification,
}: {
  state: RealtimeConnectionState;
  lastUpdateAt: string | null;
  notification: RealtimeNotificationView | null;
}) {
  return (
    <aside className={`vm-realtime vm-realtime--${state}`} aria-live="polite">
      <div>
        <strong>Cập nhật thời gian thực</strong>
        <span>{label(state)}</span>
      </div>
      <p>
        {lastUpdateAt
          ? `Thông báo backend gần nhất ${formatTimestamp(lastUpdateAt)}`
          : "Đang chờ thông báo từ backend."}
      </p>
      {notification && (
        <p>
          Nhận cập nhật mới cho {notification.resourceHint.replaceAll("_", " ")}
          ; dữ liệu thẩm quyền đang được tải lại.
        </p>
      )}
      <small>
        Thông báo chỉ là tín hiệu làm mới; dữ liệu thẩm quyền luôn được lấy lại
        từ API backend.
      </small>
    </aside>
  );
}

function label(state: RealtimeConnectionState) {
  if (state === "connected") return "đang kết nối";
  if (state === "reconnecting") return "đang kết nối lại";
  if (state === "disconnected") return "đã mất kết nối";
  return "đang mở kết nối";
}
