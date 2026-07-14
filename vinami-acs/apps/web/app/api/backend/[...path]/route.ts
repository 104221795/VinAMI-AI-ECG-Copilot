import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { serverConfig } from "@web/shared/config/server";

const allowedPaths = [
  /^health$/,
  /^ready$/,
  /^api\/v1\/identity\/session$/,
  /^api\/v1\/clinical-cases$/,
  /^api\/v1\/clinical-cases\/[0-9a-f-]+(?:\/timeline|\/audit|\/triage|\/triage\/history|\/vitals|\/vitals\/latest|\/triage-vitals-summary)?$/,
  /^api\/v1\/clinical-cases\/[0-9a-f-]+\/ecg-workspace$/,
  /^api\/v1\/ecg-studies\/[0-9a-f-]+\/(?:waveform|quality|analyses|physician-interpretations)$/,
  /^api\/v1\/encounters\/[0-9a-f-]+$/,
  /^api\/v1\/patients\/[0-9a-f-]+$/,
];

const allowedCommandPaths = [
  /^api\/v1\/clinical-cases\/[0-9a-f-]+\/triage-assessments$/,
  /^api\/v1\/clinical-cases\/[0-9a-f-]+\/triage-assessments\/[0-9a-f-]+\/corrections$/,
  /^api\/v1\/clinical-cases\/[0-9a-f-]+\/vital-observation-sets$/,
  /^api\/v1\/clinical-cases\/[0-9a-f-]+\/vital-observation-sets\/[0-9a-f-]+\/corrections$/,
  /^api\/v1\/clinical-cases\/[0-9a-f-]+\/ecg-studies$/,
  /^api\/v1\/ecg-studies\/[0-9a-f-]+\/(?:analyses|physician-interpretations)$/,
];

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return forward(request, context, "GET", allowedPaths);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  return forward(request, context, "POST", allowedCommandPaths);
}

async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
  method: "GET" | "POST",
  allowList: RegExp[],
) {
  const { path } = await context.params;
  const joined = path.join("/");
  if (!allowList.some((pattern) => pattern.test(joined))) {
    return problem(
      404,
      "Unsupported frontend resource",
      "This resource is not exposed through the approved frontend boundary.",
    );
  }
  const correlationId =
    validUuid(request.headers.get("x-correlation-id")) ?? crypto.randomUUID();
  const target = new URL(
    joined,
    `${serverConfig.apiBaseUrl.replace(/\/$/, "")}/`,
  );
  target.search = request.nextUrl.search;
  const headers = new Headers({
    Accept: "application/json",
    "X-Correlation-ID": correlationId,
    "X-Request-Source": "vinami-next-bff",
  });
  if (method === "POST") {
    const contentType = request.headers.get("content-type");
    if (contentType) headers.set("Content-Type", contentType);
    const idempotencyKey = request.headers.get("idempotency-key");
    if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
  }
  if (serverConfig.identityMode === "development") {
    headers.set("X-Development-Identity", serverConfig.developmentIdentity);
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 9_000);
  try {
    const response = await fetch(target, {
      method,
      headers,
      body: method === "POST" ? await request.arrayBuffer() : undefined,
      cache: "no-store",
      signal: controller.signal,
    });
    return new NextResponse(response.body, {
      status: response.status,
      headers: {
        "content-type":
          response.headers.get("content-type") ?? "application/json",
        "x-correlation-id":
          response.headers.get("x-correlation-id") ?? correlationId,
        "cache-control": "no-store",
      },
    });
  } catch (error) {
    const timeoutFailure =
      error instanceof DOMException && error.name === "AbortError";
    return problem(
      timeoutFailure ? 504 : 503,
      timeoutFailure ? "Upstream timeout" : "Upstream unavailable",
      timeoutFailure
        ? "The clinical service did not respond in time."
        : "The clinical service could not be reached.",
      correlationId,
    );
  } finally {
    clearTimeout(timeout);
  }
}

function validUuid(value: string | null): string | null {
  return value &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
    ? value
    : null;
}

function problem(
  status: number,
  title: string,
  detail: string,
  correlationId = crypto.randomUUID(),
) {
  return NextResponse.json(
    {
      type: "https://vinami.example/problems/frontend-boundary",
      title,
      status,
      detail,
      instance: "frontend-boundary",
      correlation_id: correlationId,
    },
    {
      status,
      headers: {
        "content-type": "application/problem+json",
        "x-correlation-id": correlationId,
      },
    },
  );
}
