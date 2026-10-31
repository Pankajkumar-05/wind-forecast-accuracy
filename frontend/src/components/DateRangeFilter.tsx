import { useEffect, useState } from "react";
import type { DateRange } from "../types/api";
import { addDays } from "../utils/format";

interface DateRangeFilterProps {
  value: DateRange;
  min: string;
  max: string;
  onChange: (range: DateRange) => void;
}

/** Validates a draft range against the supported window. Returns an error message or null. */
export function validateRange(range: DateRange, min: string, max: string): string | null {
  if (!range.start || !range.end) return "Choose both a start and an end date.";
  if (range.start > range.end) return "The start date must not be after the end date.";
  if (range.start < min || range.end > max) return `Dates must be between ${min} and ${max}.`;
  return null;
}

export function DateRangeFilter({ value, min, max, onChange }: DateRangeFilterProps) {
  const [draft, setDraft] = useState<DateRange>(value);
  const error = validateRange(draft, min, max);

  useEffect(() => setDraft(value), [value]);

  function update(next: DateRange) {
    setDraft(next);
    if (!validateRange(next, min, max)) onChange(next);
  }

  const presets: { label: string; range: DateRange }[] = [
    { label: "Full period", range: { start: min, end: max } },
    { label: "Last 14 days", range: { start: addDays(max, -13) < min ? min : addDays(max, -13), end: max } },
    { label: "Last 7 days", range: { start: addDays(max, -6) < min ? min : addDays(max, -6), end: max } },
    { label: "Last day", range: { start: max, end: max } },
  ];

  return (
    <div className="filter" role="group" aria-label="Delivery date filter">
      <div className="filter__presets">
        {presets.map((preset) => {
          const active = preset.range.start === value.start && preset.range.end === value.end;
          return (
            <button
              key={preset.label}
              type="button"
              className={`chip${active ? " chip--active" : ""}`}
              aria-pressed={active}
              onClick={() => update(preset.range)}
            >
              {preset.label}
            </button>
          );
        })}
      </div>
      <div className="filter__inputs">
        <label>
          <span>From</span>
          <input type="date" value={draft.start} min={min} max={max} onChange={(e) => update({ ...draft, start: e.target.value })} />
        </label>
        <label>
          <span>To</span>
          <input type="date" value={draft.end} min={min} max={max} onChange={(e) => update({ ...draft, end: e.target.value })} />
        </label>
      </div>
      {error && (
        <p className="filter__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
