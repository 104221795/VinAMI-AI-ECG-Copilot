import { describe, expect, it } from "vitest";
import { mapApiError } from "./index";

describe("mapApiError", () => {
  it("preserves the RFC 7807 correlation ID", () => {
    const error = mapApiError(403, {
      type: "urn:test",
      title: "Denied",
      status: 403,
      detail: "Verified identity lacks permission",
      instance: "/safe",
      correlation_id: "7fc88d15-f71f-4baf-b65a-741d05058f08",
    });
    expect(error.kind).toBe("authorization");
    expect(error.correlationId).toBe("7fc88d15-f71f-4baf-b65a-741d05058f08");
  });

  it("maps transient server failures to a retryable error", () => {
    const error = mapApiError(503, {});
    expect(error.kind).toBe("server");
    expect(error.retryable).toBe(true);
  });
});
