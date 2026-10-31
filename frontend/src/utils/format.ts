// All times are shown in UK local time, because that is the clock the market and the buyers use.
const UK_TIMEZONE = "Europe/London";

const dateTimeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: UK_TIMEZONE,
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const shortDateTimeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: UK_TIMEZONE,
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const timeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: UK_TIMEZONE,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const dayFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: UK_TIMEZONE,
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
});
const dayShortFormat = new Intl.DateTimeFormat("en-GB", { timeZone: UK_TIMEZONE, day: "numeric", month: "short" });

const EM_DASH = "—";

export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso));
}

export function formatShortDateTime(valueMs: number): string {
  return shortDateTimeFormat.format(new Date(valueMs));
}

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso));
}

/** "2026-01-11" -> "Sun, 11 Jan 2026". Parsed at midday UTC so the calendar day never shifts. */
export function formatDeliveryDay(isoDate: string): string {
  return dayFormat.format(new Date(`${isoDate}T12:00:00Z`));
}

export function formatDayShort(valueMs: number): string {
  return dayShortFormat.format(new Date(valueMs));
}

export function formatDayShortFromIsoDate(isoDate: string): string {
  return dayShortFormat.format(new Date(`${isoDate}T12:00:00Z`));
}

export function formatMW(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`;
}

/** Signed, with an explicit "+" so over-forecasts are obvious. */
export function formatSignedMW(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EM_DASH;
  return `${value.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })}%`;
}

export function formatInteger(value: number): string {
  return value.toLocaleString("en-GB");
}

/** Plain-English reading of the bias sign, shown under the Bias KPI. */
export function describeBias(bias: number | null): string {
  if (bias === null) return "Not enough data";
  if (Math.abs(bias) < 1) return "No systematic lean";
  return bias > 0 ? "Forecasts lean too high (over-forecast)" : "Forecasts lean too low (under-forecast)";
}

/** Adds days to a YYYY-MM-DD string without touching timezones. */
export function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** "hourly", "half-hourly" or "N-minute" for a forecast resolution in minutes. */
export function describeResolution(minutes: number): string {
  if (minutes === 60) return "hourly";
  if (minutes === 30) return "half-hourly";
  return `${minutes}-minute`;
}
