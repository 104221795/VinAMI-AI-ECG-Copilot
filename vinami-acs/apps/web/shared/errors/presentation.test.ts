import { describe, expect, it } from "vitest";
import { VinamiApiError } from "@vinami/api-client";
import { presentError } from "./presentation";

describe("error presentation", () => {
  it.each([
    ["authentication", "Session unavailable"],
    ["authorization", "Permission required"],
    ["not_found", "Record not found"],
    ["conflict", "Information changed"],
    ["validation", "Request could not be validated"],
    ["timeout", "Service response delayed"],
    ["offline", "Connection unavailable"],
    ["server", "Clinical service unavailable"],
    ["malformed", "Contract mismatch detected"],
  ] as const)("maps %s distinctly", (kind, title) => {
    expect(
      presentError(new VinamiApiError(kind, "safe", 500, "corr", true)).title,
    ).toBe(title);
  });
});
