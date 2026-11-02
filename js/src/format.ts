/**
 * Money, percentages, dates and sizes as people read and type them. Every formatter takes the
 * Intl locale to write in, which an application usually gets from `Language.intlLocale()`.
 *
 * Amounts travel as whole cents and shares as basis points (1/100 of a percent), so that sums add
 * up exactly; only the formatters turn them into text and back.
 */

/** Cents as euros: "€287.59" in English, "287,59 €" in Portuguese. */
export function euros(cents: number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency: "EUR" }).format(cents / 100);
}

/** Cents as the plain number an amount field shows for editing: "287.59" or "287,59". */
export function amountInput(cents: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: false,
  }).format(cents / 100);
}

/**
 * An amount typed by a person, as cents, or null when the text is not an amount.
 *
 * Either separator may be the decimal one, so "287,59" and "287.59" both work. With both present
 * the last is the decimal and the other groups thousands ("1.234,56", "1,234.56"); a separator
 * that appears more than once, or once before exactly three digits, groups thousands ("1.234").
 * Groups must be of three digits, and more than two decimals is not an amount. Spaces and a euro
 * sign are ignored, and a leading minus (or the minus sign) makes it negative.
 */
export function parseAmount(text: string): number | null {
  let value = text.replace(/[\s €]/g, "");
  let sign = 1;
  if (value.startsWith("-") || value.startsWith("−")) {
    sign = -1;
    value = value.slice(1);
  }
  let whole = value;
  let fraction = "";
  const decimalAt = Math.max(value.lastIndexOf("."), value.lastIndexOf(","));
  if (decimalAt >= 0) {
    const separator = value.charAt(decimalAt);
    const other = separator === "." ? "," : ".";
    const grouping =
      value.includes(other) || value.indexOf(separator) !== decimalAt || value.length - decimalAt - 1 === 3;
    if (value.includes(other)) {
      whole = value.slice(0, decimalAt);
      fraction = value.slice(decimalAt + 1);
      if (!grouped(whole, other)) return null;
      whole = whole.split(other).join("");
    } else if (grouping) {
      if (!grouped(value, separator)) return null;
      whole = value.split(separator).join("");
    } else {
      whole = value.slice(0, decimalAt);
      fraction = value.slice(decimalAt + 1);
    }
  }
  if (!/^\d*$/.test(whole) || !/^\d{0,2}$/.test(fraction) || !(whole + fraction)) return null;
  const cents = Number(whole || "0") * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(cents) ? sign * cents : null;
}

/** Whether `digits` is digits grouped in threes by `separator`: "1.234.567". */
function grouped(digits: string, separator: string): boolean {
  const [first = "", ...rest] = digits.split(separator);
  return /^\d{1,3}$/.test(first) && rest.every((group) => /^\d{3}$/.test(group));
}

/** Basis points as a percentage: 5000 → "50%", 3333 → "33.33%" (or "33,33 %"). */
export function percent(basisPoints: number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 2 }).format(basisPoints / 10_000);
}

/** A percentage typed by a person ("25", "33,33", "12.5%"), as basis points, or null; at most 100%. */
export function parsePercent(text: string): number | null {
  const value = text.replace(/[\s%]/g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return null;
  const basisPoints = Math.round(Number(value) * 100);
  return basisPoints <= 10_000 ? basisPoints : null;
}

/** Basis points as the plain number a share field shows: 2500 → "25", 3333 → "33.33". */
export function percentInput(basisPoints: number): string {
  return String(basisPoints / 100);
}

/** An ISO date (YYYY-MM-DD) as people read it: "18 Oct 2026" in British English. */
export function day(iso: string, locale: string): string {
  const [year = 0, month = 1, date = 1] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(
    new Date(Date.UTC(year, month - 1, date)),
  );
}

/**
 * A moment as people read it: "18 Oct 2026, 14:05" in British English, in `timeZone`, or the
 * reader's own when it is left out.
 */
export function moment(iso: string, locale: string, timeZone?: string): string {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso));
}

/** A month's name, 1 for January: "October", "outubro". */
export function monthName(month: number, locale: string): string {
  return new Intl.DateTimeFormat(locale, { month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2026, month - 1, 1)));
}

/**
 * A moment's calendar date as ISO (YYYY-MM-DD) in `timeZone`, or the reader's own when it is left
 * out. Read from the date's parts rather than any locale's pattern, which a browser's locale data
 * can change.
 */
export function calendarDate(at: Date = new Date(), timeZone?: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone,
  }).formatToParts(at);
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

/**
 * Whether a moment falls today, tomorrow or on another day, by the calendar in `timeZone` (the
 * reader's own when it is left out). Tomorrow is the calendar's next date, not the date a day from
 * now: a day can be 23 or 25 hours long.
 */
export function whichDay(iso: string, now: Date = new Date(), timeZone?: string): "today" | "tomorrow" | "other" {
  const date = calendarDate(new Date(iso), timeZone);
  const today = calendarDate(now, timeZone);
  if (date === today) return "today";
  const [year = 0, month = 1, dayOfMonth = 1] = today.split("-").map(Number);
  return date === new Date(Date.UTC(year, month - 1, dayOfMonth + 1)).toISOString().slice(0, 10) ? "tomorrow" : "other";
}

/** The place a time zone is named after: "Europe/Lisbon" is Lisbon, "America/New_York" New York. */
export function zoneCity(timeZone: string): string {
  return timeZone.slice(timeZone.lastIndexOf("/") + 1).replaceAll("_", " ");
}

/** A file's size as people read it: "312 kB", "4.2 MB"; never less than one kilobyte. */
export function fileSize(bytes: number, locale: string): string {
  const [value, unit] = bytes >= 1_000_000 ? [bytes / 1_000_000, "megabyte"] : [Math.max(bytes / 1000, 1), "kilobyte"];
  return new Intl.NumberFormat(locale, { style: "unit", unit, maximumFractionDigits: value < 10 ? 1 : 0 }).format(value);
}
