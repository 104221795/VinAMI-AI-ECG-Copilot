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
        <strong>Real-time updates</strong>
        <span>{label(state)}</span>
      </div>
      <p>
        {lastUpdateAt
          ? `Last backend notification ${formatTimestamp(lastUpdateAt)}`
          : "Waiting for backend notifications."}
      </p>
      {notification && (
        <p>
          New {notification.resourceHint.replaceAll("_", " ")} update received;
          authoritative data is refreshing.
        </p>
      )}
      <small>
        Notifications are not clinical truth; the UI refetches backend APIs.
      </small>
    </aside>
  );
}

function label(state: RealtimeConnectionState) {
  if (state === "connected") return "connected";
  if (state === "reconnecting") return "reconnecting";
  if (state === "disconnected") return "disconnected";
  return "connecting";
}
