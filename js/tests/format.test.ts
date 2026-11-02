import { describe, expect, it } from "vitest";
import {
  amountInput,
  calendarDate,
  day,
  euros,
  fileSize,
  moment,
  monthName,
  parseAmount,
  parsePercent,
  percent,
  percentInput,
  whichDay,
  zoneCity,
} from "../src/format";

const nbsp = (text: string) => text.replace(/[\u00a0\u202f]/g, " ");

describe("euros", () => {
  it("writes euros as each language does", () => {
    expect(euros(28759, "en-GB")).toBe("€287.59");
    expect(nbsp(euros(28759, "pt-PT"))).toBe("287,59 €");
    expect(euros(-501, "en-GB")).toBe("-€5.01");
  });

  it("shows cents as a plain number to edit", () => {
    expect(amountInput(28759, "en-GB")).toBe("287.59");
    expect(amountInput(123456, "pt-PT")).toBe("1234,56");
    expect(amountInput(-5, "en-GB")).toBe("-0.05");
  });
});

describe("parseAmount", () => {
  it.each([
    ["287,59", 28759],
    ["287.59", 28759],
    ["322", 32200],
    ["322,5", 32250],
    ["0,05", 5],
    [",5", 50],
    ["1.234,56", 123456],
    ["1,234.56", 123456],
    ["1 234,56", 123456],
    ["1.234", 123400],
    ["1.234.567", 123456700],
    ["€ 12,50", 1250],
    ["12,50 €", 1250],
    ["-5", -500],
    ["−3,10", -310],
  ])("reads %s as %i cents", (text, cents) => {
    expect(parseAmount(text)).toBe(cents);
  });

  it.each(["", "abc", "1,2,3.4.5", "12,345,6", "12.3456", "1e5", "--1", "€", "1,234.567", "12,34.5", "1.2345,6"])(
    "refuses %s",
    (text) => {
      expect(parseAmount(text)).toBeNull();
    },
  );

  it("refuses an amount too large to be exact", () => {
    expect(parseAmount("99999999999999999")).toBeNull();
  });
});

describe("percentages", () => {
  it("writes basis points as a percentage", () => {
    expect(percent(5000, "en-GB")).toBe("50%");
    expect(percent(3333, "en-GB")).toBe("33.33%");
    expect(nbsp(percent(2500, "pt-PT"))).toBe("25%");
    expect(percentInput(3333)).toBe("33.33");
  });

  it.each([
    ["25", 2500],
    ["33,33", 3333],
    ["12.5%", 1250],
    ["100", 10000],
    [" 0 ", 0],
  ])("reads %s as %i basis points", (text, basisPoints) => {
    expect(parsePercent(text)).toBe(basisPoints);
  });

  it.each(["", "abc", "100.01", "150", "1.234", "-5"])("refuses %s", (text) => {
    expect(parsePercent(text)).toBeNull();
  });
});

describe("dates", () => {
  it("writes a day as each language does, day first", () => {
    expect(day("2026-10-18", "en-GB")).toBe("18 Oct 2026");
    expect(day("2026-07-06", "pt-PT")).toBe("6/07/2026");
  });

  it("writes a moment with its time, in a time zone when given one", () => {
    expect(moment("2026-10-18T14:05:00Z", "en-GB")).toMatch(/18 Oct 2026, \d\d:\d\d/);
    expect(moment("2026-10-18T14:05:00Z", "en-GB", "Europe/Lisbon")).toBe("18 Oct 2026, 15:05");
    expect(moment("2026-10-18T23:05:00Z", "en-GB", "Asia/Tokyo")).toBe("19 Oct 2026, 08:05");
  });

  it("names months", () => {
    expect(monthName(10, "en-GB")).toBe("October");
    expect(monthName(1, "pt-PT")).toBe("janeiro");
  });

  it("gives a moment's calendar date, in the reader's own zone or a given one", () => {
    expect(calendarDate(new Date(2026, 9, 26, 23, 30))).toBe("2026-10-26");
    const late = new Date("2026-10-26T23:30:00Z");
    expect(calendarDate(late, "UTC")).toBe("2026-10-26");
    expect(calendarDate(late, "Asia/Tokyo")).toBe("2026-10-27");
    expect(calendarDate(late, "America/New_York")).toBe("2026-10-26");
  });

  it("says whether a moment is today, tomorrow or another day where it is", () => {
    const now = new Date("2026-10-25T10:00:00Z");
    expect(whichDay("2026-10-25T23:00:00Z", now, "UTC")).toBe("today");
    expect(whichDay("2026-10-26T00:30:00Z", now, "UTC")).toBe("tomorrow");
    expect(whichDay("2026-10-27T00:30:00Z", now, "UTC")).toBe("other");
    expect(whichDay("2026-10-24T12:00:00Z", now, "UTC")).toBe("other");
    // Tokyo is already on the 25th's evening, so 16:00 UTC is its 26th.
    expect(whichDay("2026-10-25T16:00:00Z", now, "Asia/Tokyo")).toBe("tomorrow");
  });

  it("finds tomorrow across a month's end", () => {
    const now = new Date("2026-10-31T12:00:00Z");
    expect(whichDay("2026-11-01T06:00:00Z", now, "UTC")).toBe("tomorrow");
  });

  it("names the city a time zone is named after", () => {
    expect(zoneCity("Europe/Lisbon")).toBe("Lisbon");
    expect(zoneCity("America/New_York")).toBe("New York");
    expect(zoneCity("America/Argentina/Buenos_Aires")).toBe("Buenos Aires");
    expect(zoneCity("UTC")).toBe("UTC");
  });
});

describe("fileSize", () => {
  it("writes a size in kilobytes or megabytes", () => {
    expect(fileSize(312_000, "en-GB")).toBe("312 kB");
    expect(fileSize(200, "en-GB")).toBe("1 kB");
    expect(fileSize(2_450_000, "en-GB")).toBe("2.5 MB");
    expect(fileSize(24_500_000, "en-GB")).toBe("25 MB");
  });
});
