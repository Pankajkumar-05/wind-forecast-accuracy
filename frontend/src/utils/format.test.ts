import { addDays, describeBias, describeResolution, formatDateTime, formatDeliveryDay, formatMW, formatPercent, formatSignedMW } from "./format";

describe("number formatting", () => {
  it("formats megawatts with thousands separators", () => {
    expect(formatMW(12345.6)).toBe("12,346 MW");
    expect(formatMW(12345.6, 1)).toBe("12,345.6 MW");
  });

  it("shows a dash instead of NaN or null", () => {
    expect(formatMW(null)).toBe("—");
    expect(formatMW(undefined)).toBe("—");
    expect(formatMW(Number.NaN)).toBe("—");
    expect(formatPercent(null)).toBe("—");
    expect(formatSignedMW(null)).toBe("—");
  });

  it("keeps zero as a real value", () => {
    expect(formatMW(0)).toBe("0 MW");
  });

  it("adds an explicit sign to errors", () => {
    expect(formatSignedMW(250)).toBe("+250 MW");
    expect(formatSignedMW(-250)).toBe("−250 MW");
    expect(formatSignedMW(0)).toBe("0 MW");
  });

  it("formats percentages", () => {
    expect(formatPercent(14.234)).toBe("14.2%");
  });
});

describe("bias description", () => {
  it("explains the sign in plain English", () => {
    expect(describeBias(150)).toMatch(/too high/i);
    expect(describeBias(-150)).toMatch(/too low/i);
    expect(describeBias(0.2)).toMatch(/no systematic/i);
    expect(describeBias(null)).toMatch(/not enough data/i);
  });
});

describe("date and time formatting (UK local time)", () => {
  it("shows winter timestamps in GMT", () => {
    expect(formatDateTime("2026-01-15T09:00:00Z")).toContain("09:00");
  });

  it("converts to British Summer Time when applicable", () => {
    expect(formatDateTime("2026-07-15T09:00:00Z")).toContain("10:00");
  });

  it("formats a delivery day without shifting the calendar date", () => {
    expect(formatDeliveryDay("2026-01-11")).toBe("Sun, 11 Jan 2026");
  });

  it("adds days across month boundaries", () => {
    expect(addDays("2026-01-31", 1)).toBe("2026-02-01");
    expect(addDays("2026-02-01", -13)).toBe("2026-01-19");
  });
});

describe("describeResolution", () => {
  it("names common forecast resolutions", () => {
    expect(describeResolution(60)).toBe("hourly");
    expect(describeResolution(30)).toBe("half-hourly");
    expect(describeResolution(90)).toBe("90-minute");
  });
});
