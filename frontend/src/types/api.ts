// Mirrors backend/app/schemas/api.py. Timestamps are ISO-8601 UTC strings; dates are YYYY-MM-DD.

export interface DecisionRuleInfo {
  cutoff_time: string;
  timezone: string;
  days_ahead: number;
  description: string;
}

export interface ConfigResponse {
  data_source: string;
  window_start: string;
  window_end: string;
  decision_rule: DecisionRuleInfo;
  mape_min_actual_mw: number;
  forecast_resolution_minutes: number;
}

/**
 * Coverage is measured on the FORECAST grid (hourly for WINDFOR), not the 30-minute actuals grid.
 * Actual periods that fall between forecast targets are informational, not missing data.
 */
export interface Coverage {
  forecast_resolution_minutes: number;
  expected_forecast_periods: number;
  forecast_periods: number;
  actual_periods_on_forecast_grid: number;
  matched_periods: number;
  missing_forecast_periods: number;
  missing_actual_periods: number;
  forecast_periods_off_grid: number;
  actual_periods_total: number;
  actual_periods_off_forecast_grid: number;
}

export interface DataQuality {
  coverage: Coverage;
  warnings: string[];
  malformed_rows_skipped: number;
  duplicates_removed: number;
  forecasts_published_after_cutoff_excluded: number;
  fetched_at: string;
}

export interface ComparisonPoint {
  start_time: string;
  delivery_date: string;
  forecast_mw: number;
  actual_mw: number;
  forecast_publish_time: string;
  lead_time_hours: number;
  error_mw: number;
  abs_error_mw: number;
  pct_error: number | null;
}

export interface ComparisonResponse {
  start: string;
  end: string;
  points: ComparisonPoint[];
  quality: DataQuality;
}

export interface Metrics {
  n: number;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  mape: number | null;
  mape_n: number;
  mape_excluded: number;
  mean_actual: number | null;
  mean_forecast: number | null;
  mae_pct_of_mean_actual: number | null;
  p90_abs_error: number | null;
  max_abs_error: number | null;
}

export interface DailyMetrics {
  delivery_date: string;
  n: number;
  mae: number;
  bias: number;
  rmse: number;
}

export interface MetricsResponse {
  start: string;
  end: string;
  overall: Metrics;
  daily: DailyMetrics[];
  quality: DataQuality;
}

export interface LatestForecastPeriod {
  start_time: string;
  publish_time: string;
  forecast_mw: number;
}

export interface LatestForecastResponse {
  delivery_date: string;
  decision_cutoff: string;
  latest_publish_time: string;
  earliest_publish_time: string;
  period_count: number;
  mean_mw: number;
  peak_mw: number;
  peak_time: string;
  min_mw: number;
  actual_mean_mw: number | null;
  periods: LatestForecastPeriod[];
}

export interface DateRange {
  start: string;
  end: string;
}
