import { describe, expect, it, vi } from "vitest";
import {
  formatDueLabel,
  formatDueRelative,
  formatRelative,
  formatTimestamp,
  formatUnknownEnum,
  isUnsetTimestamp,
  safeDemographics,
  shortReference,
} from "./index";

describe("clinical formatting", () => {
  it("formats safe references and demographics", () => {
    expect(shortReference("cbbc0872-798f-40c5-83e3-64d66176e73b", "CASE")).toBe(
      "CASE-CBBC0872",
    );
    expect(safeDemographics("45-64", "female")).toBe("Tuổi 45-64 | female");
  });

  it("formats UTC and relative timestamps deterministically", () => {
    vi.setSystemTime(new Date("2026-07-13T15:00:00Z"));
    expect(formatTimestamp("2026-07-13T14:44:00Z")).toContain("UTC");
    expect(formatRelative("2026-07-13T14:44:00Z")).toContain("phút");
    vi.useRealTimers();
  });

  it("does not leak epoch or placeholder timestamps into clinical UI", () => {
    expect(isUnsetTimestamp(null)).toBe(true);
    expect(isUnsetTimestamp("1970-01-01T00:00:00Z")).toBe(true);
    expect(isUnsetTimestamp("2020-01-01T00:00:00Z")).toBe(true);
    expect(formatTimestamp("2020-01-01T00:00:00Z")).toBe(
      "Chưa ghi nhận thời gian",
    );
    expect(formatDueLabel("2020-01-01T00:00:00Z")).toBe("Chưa đặt hạn xử lý");
    expect(formatDueRelative(null)).toBe("Chưa đặt hạn xử lý");
  });

  it("maps unknown enum values without throwing", () => {
    expect(formatUnknownEnum("future_state", ["open"]).label).toBe(
      "Chưa rõ (future_state)",
    );
    expect(formatUnknownEnum("future_state", ["open"]).unknown).toBe(true);
  });
});
