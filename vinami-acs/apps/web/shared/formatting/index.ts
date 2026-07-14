const dateTime = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

export function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Invalid timestamp"
    : `${dateTime.format(parsed)} UTC`;
}

export function formatRelative(value: string, now = Date.now()): string {
  const parsed = new Date(value).getTime();
  if (Number.isNaN(parsed)) return "unknown time";
  const seconds = Math.round((parsed - now) / 1000);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (Math.abs(seconds) < 60) return formatter.format(seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
  return formatter.format(Math.round(hours / 24), "day");
}

export function shortReference(value: string, prefix = "REF"): string {
  return `${prefix}-${value.slice(0, 8).toUpperCase()}`;
}

export function safeDemographics(
  ageBand?: string | null,
  sexAtBirth?: string | null,
): string {
  const facts = [
    ageBand ? `Age ${ageBand}` : null,
    sexAtBirth ? sexAtBirth : null,
  ].filter(Boolean);
  return facts.length ? facts.join(" · ") : "Demographics not recorded";
}

export function formatUnknownEnum(
  value: string,
  known: readonly string[],
): { label: string; unknown: boolean } {
  if (!known.includes(value))
    return { label: `Unknown (${value})`, unknown: true };
  return { label: value.replaceAll("_", " "), unknown: false };
}
