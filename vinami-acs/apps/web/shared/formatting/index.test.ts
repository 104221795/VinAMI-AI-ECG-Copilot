import { describe, expect, it, vi } from "vitest";
import {
  formatRelative,
  formatTimestamp,
  formatUnknownEnum,
  safeDemographics,
  shortReference,
} from "./index";

describe("clinical formatting", () => {
  it("formats safe references and demographics", () => {
    expect(shortReference("cbbc0872-798f-40c5-83e3-64d66176e73b", "CASE")).toBe(
      "CASE-CBBC0872",
    );
    expect(safeDemographics("45-64", "female")).toBe("Age 45-64 · female");
  });

  it("formats UTC and relative timestamps deterministically", () => {
    vi.setSystemTime(new Date("2026-07-13T15:00:00Z"));
    expect(formatTimestamp("2026-07-13T14:44:00Z")).toContain("UTC");
    expect(formatRelative("2026-07-13T14:44:00Z")).toContain("minute");
    vi.useRealTimers();
  });

  it("maps unknown enum values without throwing", () => {
    expect(formatUnknownEnum("future_state", ["open"]).label).toBe(
      "Unknown (future_state)",
    );
    expect(formatUnknownEnum("future_state", ["open"]).unknown).toBe(true);
  });
});
