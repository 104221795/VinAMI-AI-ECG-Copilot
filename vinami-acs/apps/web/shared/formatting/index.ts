const dateTime = new Intl.DateTimeFormat("vi-VN", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

const PLACEHOLDER_2020_UTC = Date.UTC(2020, 0, 1, 0, 0, 0, 0);

export function isUnsetTimestamp(value?: string | null): boolean {
  if (!value?.trim()) return true;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return false;
  const utcYear = parsed.getUTCFullYear();
  return (
    utcYear <= 1971 ||
    value.startsWith("0001-01-01") ||
    parsed.getTime() === PLACEHOLDER_2020_UTC
  );
}

export function formatTimestamp(
  value?: string | null,
  fallback = "Chưa ghi nhận thời gian",
): string {
  if (isUnsetTimestamp(value)) return fallback;
  const parsed = new Date(value ?? "");
  return Number.isNaN(parsed.getTime())
    ? "Thời gian không hợp lệ"
    : `${dateTime.format(parsed)} UTC`;
}

export function formatRelative(
  value?: string | null,
  now = Date.now(),
  fallback = "chưa rõ thời gian",
): string {
  if (isUnsetTimestamp(value)) return fallback;
  const parsed = new Date(value ?? "").getTime();
  if (Number.isNaN(parsed)) return fallback;
  const seconds = Math.round((parsed - now) / 1000);
  const formatter = new Intl.RelativeTimeFormat("vi", { numeric: "auto" });
  if (Math.abs(seconds) < 60) return formatter.format(seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  return formatter.format(Math.round(hours / 24), "day");
}

export function formatDueTimestamp(value?: string | null): string {
  return formatTimestamp(value, "Chưa đặt hạn xử lý");
}

export function formatDueLabel(value?: string | null): string {
  return isUnsetTimestamp(value)
    ? "Chưa đặt hạn xử lý"
    : `Hạn xử lý ${formatTimestamp(value)}`;
}

export function formatDueRelative(
  value?: string | null,
  now = Date.now(),
): string {
  return formatRelative(value, now, "Chưa đặt hạn xử lý");
}

export function shortReference(value: string, prefix = "REF"): string {
  return `${prefix}-${value.slice(0, 8).toUpperCase()}`;
}

export function safeDemographics(
  ageBand?: string | null,
  sexAtBirth?: string | null,
): string {
  const facts = [
    ageBand ? `Tuổi ${ageBand}` : null,
    sexAtBirth ? sexAtBirth : null,
  ].filter(Boolean);
  return facts.length ? facts.join(" | ") : "Chưa ghi nhận nhân khẩu học";
}

export function formatUnknownEnum(
  value: string,
  known: readonly string[],
): { label: string; unknown: boolean } {
  if (!known.includes(value))
    return { label: `Chưa rõ (${value})`, unknown: true };
  return { label: value.replaceAll("_", " "), unknown: false };
}
