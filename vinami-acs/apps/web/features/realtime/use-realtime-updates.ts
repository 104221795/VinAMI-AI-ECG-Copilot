"use client";

import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

export type RealtimeConnectionState =
  "connecting" | "connected" | "reconnecting" | "disconnected";

export interface RealtimeNotificationView {
  eventId: string;
  eventType: string;
  resourceHint: string;
  occurredAt: string;
}

export function useRealtimeUpdates({
  caseId,
  invalidate,
}: {
  caseId?: string;
  invalidate: QueryKey[];
}) {
  const queryClient = useQueryClient();
  const seen = useRef(new Set<string>());
  const [state, setState] = useState<RealtimeConnectionState>("connecting");
  const [lastUpdateAt, setLastUpdateAt] = useState<string | null>(null);
  const [notification, setNotification] =
    useState<RealtimeNotificationView | null>(null);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      setState("disconnected");
      return;
    }
    const query = caseId ? `?case_id=${encodeURIComponent(caseId)}` : "";
    const source = new EventSource(`/api/realtime/events${query}`);
    setState("connecting");
    source.onopen = () => setState("connected");
    source.onerror = () =>
      setState((value) =>
        value === "connected" ? "reconnecting" : "disconnected",
      );
    source.onmessage = (event) => {
      handleEvent(event.data);
    };
    for (const eventName of [
      "ecg",
      "troponin",
      "clinical_reasoning",
      "tasks",
      "alerts",
      "outcomes",
      "integration",
      "case",
    ]) {
      source.addEventListener(eventName, (event) => {
        handleEvent((event as MessageEvent<string>).data);
      });
    }
    function handleEvent(raw: string) {
      try {
        const payload = JSON.parse(raw) as Record<string, unknown>;
        const eventId = String(payload.event_id ?? "");
        if (!eventId || seen.current.has(eventId)) return;
        seen.current.add(eventId);
        const occurredAt = String(
          payload.occurred_at ?? new Date().toISOString(),
        );
        setLastUpdateAt(occurredAt);
        setNotification({
          eventId,
          eventType: String(payload.event_type ?? "backend_event"),
          resourceHint: String(payload.resource_hint ?? "case"),
          occurredAt,
        });
        for (const key of invalidate) {
          void queryClient.invalidateQueries({ queryKey: key });
        }
      } catch {
        setState("reconnecting");
      }
    }
    return () => {
      source.close();
      setState("disconnected");
    };
  }, [caseId, queryClient, JSON.stringify(invalidate)]);

  return { state, lastUpdateAt, notification };
}
