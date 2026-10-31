import type {
  ComparisonResponse,
  ConfigResponse,
  DataQuality,
  LatestForecastResponse,
  MetricsResponse,
} from "../types/api";

export const config: ConfigResponse = {
  data_source: "Elexon BMRS: FUELHH (actual wind) and WINDFOR (wind forecast)",
  window_start: "2026-01-02",
  window_end: "2026-02-01",
  decision_rule: {
    cutoff_time: "09:00",
    timezone: "Europe/London",
    days_ahead: 1,
    description: "1 day(s) before delivery at 09:00 Europe/London",
  },
  mape_min_actual_mw: 50,
  forecast_resolution_minutes: 60,
};

export const goodQuality: DataQuality = {
  coverage: {
    forecast_resolution_minutes: 60,
    expected_forecast_periods: 100,
    forecast_periods: 100,
    actual_periods_on_forecast_grid: 100,
    matched_periods: 100,
    missing_forecast_periods: 0,
    missing_actual_periods: 0,
    forecast_periods_off_grid: 0,
    actual_periods_total: 200,
    actual_periods_off_forecast_grid: 100,
  },
  warnings: [],
  malformed_rows_skipped: 0,
  duplicates_removed: 0,
  forecasts_published_after_cutoff_excluded: 12,
  fetched_at: "2026-01-31T10:00:00Z",
};

export const partialQuality: DataQuality = {
  ...goodQuality,
  coverage: { ...goodQuality.coverage, matched_periods: 60, missing_actual_periods: 40, actual_periods_on_forecast_grid: 60 },
  warnings: ["40 of 100 expected forecast periods have no actual generation value (data may not be published yet) and are excluded from the error metrics."],
};

export const metrics: MetricsResponse = {
  start: "2026-01-02",
  end: "2026-02-01",
  overall: {
    n: 100,
    mae: 812.4,
    rmse: 1034.9,
    bias: -120.3,
    mape: 14.2,
    mape_n: 97,
    mape_excluded: 3,
    mean_actual: 6000,
    mean_forecast: 5880,
    mae_pct_of_mean_actual: 13.5,
    p90_abs_error: 1650,
    max_abs_error: 3100,
  },
  daily: [
    { delivery_date: "2026-01-02", n: 48, mae: 700, bias: 50, rmse: 900 },
    { delivery_date: "2026-01-03", n: 48, mae: 900, bias: -200, rmse: 1100 },
  ],
  quality: goodQuality,
};

export const comparison: ComparisonResponse = {
  start: "2026-01-02",
  end: "2026-02-01",
  points: [
    {
      start_time: "2026-01-02T00:00:00Z",
      delivery_date: "2026-01-02",
      forecast_mw: 5000,
      actual_mw: 5200,
      forecast_publish_time: "2026-01-01T08:00:00Z",
      lead_time_hours: 16,
      error_mw: -200,
      abs_error_mw: 200,
      pct_error: -3.8,
    },
    {
      start_time: "2026-01-02T00:30:00Z",
      delivery_date: "2026-01-02",
      forecast_mw: 5100,
      actual_mw: 5000,
      forecast_publish_time: "2026-01-01T08:00:00Z",
      lead_time_hours: 16.5,
      error_mw: 100,
      abs_error_mw: 100,
      pct_error: 2,
    },
  ],
  quality: goodQuality,
};

export const latest: LatestForecastResponse = {
  delivery_date: "2026-02-01",
  decision_cutoff: "2026-01-31T09:00:00Z",
  latest_publish_time: "2026-01-31T08:30:00Z",
  earliest_publish_time: "2026-01-31T08:30:00Z",
  period_count: 48,
  mean_mw: 7421.6,
  peak_mw: 9100,
  peak_time: "2026-02-01T15:00:00Z",
  min_mw: 5200,
  actual_mean_mw: 7300,
  periods: [
    { start_time: "2026-02-01T00:00:00Z", publish_time: "2026-01-31T08:30:00Z", forecast_mw: 7000 },
    { start_time: "2026-02-01T00:30:00Z", publish_time: "2026-01-31T08:30:00Z", forecast_mw: 7100 },
  ],
};
