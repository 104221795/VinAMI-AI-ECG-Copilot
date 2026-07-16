import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { serverConfig } from "@web/shared/config/server";

export async function GET(request: NextRequest) {
  const target = new URL(
    "/api/v1/realtime/events",
    serverConfig.apiBaseUrl.replace(/\/$/, ""),
  );
  target.search = request.nextUrl.search;
  const headers = new Headers({
    Accept: "text/event-stream",
    "X-Request-Source": "vinami-next-realtime-bff",
    "X-Correlation-ID":
      request.headers.get("x-correlation-id") ?? crypto.randomUUID(),
  });
  const lastEventId = request.headers.get("last-event-id");
  if (lastEventId) headers.set("Last-Event-ID", lastEventId);
  if (serverConfig.identityMode === "development") {
    headers.set("X-Development-Identity", serverConfig.developmentIdentity);
  }
  try {
    const upstream = await fetch(target, {
      headers,
      cache: "no-store",
    });
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") ?? "text/event-stream",
        "cache-control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      {
        type: "https://vinami.example/problems/realtime-upstream",
        title: "Real-time upstream unavailable",
        status: 503,
        detail: "The clinical notification stream could not be reached.",
        instance: "realtime-events",
        correlation_id: crypto.randomUUID(),
      },
      { status: 503 },
    );
  }
}
