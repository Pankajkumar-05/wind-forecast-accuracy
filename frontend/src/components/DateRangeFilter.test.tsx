import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DateRangeFilter, validateRange } from "./DateRangeFilter";

const MIN = "2026-01-02";
const MAX = "2026-02-01";

describe("validateRange", () => {
  it("accepts a valid range", () => {
    expect(validateRange({ start: "2026-01-05", end: "2026-01-10" }, MIN, MAX)).toBeNull();
  });
  it("accepts a single day", () => {
    expect(validateRange({ start: "2026-01-05", end: "2026-01-05" }, MIN, MAX)).toBeNull();
  });
  it("rejects start after end", () => {
    expect(validateRange({ start: "2026-01-10", end: "2026-01-05" }, MIN, MAX)).toMatch(/not be after/);
  });
  it("rejects dates outside the supported window", () => {
    expect(validateRange({ start: "2025-12-01", end: "2026-01-05" }, MIN, MAX)).toMatch(/between/);
    expect(validateRange({ start: "2026-01-05", end: "2026-03-01" }, MIN, MAX)).toMatch(/between/);
  });
  it("rejects empty dates", () => {
    expect(validateRange({ start: "", end: "2026-01-05" }, MIN, MAX)).toMatch(/both/);
  });
});

describe("DateRangeFilter", () => {
  it("calls onChange when a preset is chosen", async () => {
    const onChange = vi.fn();
    render(<DateRangeFilter value={{ start: MIN, end: MAX }} min={MIN} max={MAX} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Last 7 days" }));
    expect(onChange).toHaveBeenCalledWith({ start: "2026-01-26", end: MAX });
  });

  it("marks the active preset as pressed", () => {
    render(<DateRangeFilter value={{ start: MIN, end: MAX }} min={MIN} max={MAX} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Full period" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Last 7 days" })).toHaveAttribute("aria-pressed", "false");
  });

  it("does not apply an invalid range and explains why", async () => {
    const onChange = vi.fn();
    render(<DateRangeFilter value={{ start: MIN, end: "2026-01-10" }} min={MIN} max={MAX} onChange={onChange} />);
    const from = screen.getByLabelText("From");
    await userEvent.clear(from);
    await userEvent.type(from, "2026-01-20");
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/not be after/i);
  });
});
