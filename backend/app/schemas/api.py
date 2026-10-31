"""Pydantic response models: the public contract of the API (mirrored in frontend/src/types)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(_Out):
    status: str
    version: str


class DecisionRuleInfo(_Out):
    cutoff_time: str
    timezone: str
    days_ahead: int
    description: str


class ConfigResponse(_Out):
    data_source: str
    window_start: date
    window_end: date
    decision_rule: DecisionRuleInfo
    mape_min_actual_mw: float
    forecast_resolution_minutes: int


class CoverageOut(_Out):
    forecast_resolution_minutes: int
    expected_forecast_periods: int
    forecast_periods: int
    actual_periods_on_forecast_grid: int
    matched_periods: int
    missing_forecast_periods: int
    missing_actual_periods: int
    forecast_periods_off_grid: int
    actual_periods_total: int
    actual_periods_off_forecast_grid: int


class DataQualityOut(_Out):
    coverage: CoverageOut
    warnings: list[str]
    malformed_rows_skipped: int
    duplicates_removed: int
    forecasts_published_after_cutoff_excluded: int
    fetched_at: datetime


class ForecastPointOut(_Out):
    start_time: datetime
    publish_time: datetime
    forecast_mw: float
    lead_time_hours: float


class ForecastsResponse(_Out):
    start: date
    end: date
    forecasts: list[ForecastPointOut]


class ActualPointOut(_Out):
    start_time: datetime
    actual_mw: float


class ActualsResponse(_Out):
    start: date
    end: date
    actuals: list[ActualPointOut]


class ComparisonPointOut(_Out):
    start_time: datetime
    delivery_date: date
    forecast_mw: float
    actual_mw: float
    forecast_publish_time: datetime
    lead_time_hours: float
    error_mw: float
    abs_error_mw: float
    pct_error: float | None


class ComparisonResponse(_Out):
    start: date
    end: date
    points: list[ComparisonPointOut]
    quality: DataQualityOut


class MetricsOut(_Out):
    n: int
    mae: float | None
    rmse: float | None
    bias: float | None
    mape: float | None
    mape_n: int
    mape_excluded: int
    mean_actual: float | None
    mean_forecast: float | None
    mae_pct_of_mean_actual: float | None
    p90_abs_error: float | None
    max_abs_error: float | None


class DailyMetricsOut(_Out):
    delivery_date: date
    n: int
    mae: float
    bias: float
    rmse: float


class MetricsResponse(_Out):
    start: date
    end: date
    overall: MetricsOut
    daily: list[DailyMetricsOut]
    quality: DataQualityOut


class LatestForecastPeriod(_Out):
    start_time: datetime
    publish_time: datetime
    forecast_mw: float


class LatestForecastResponse(_Out):
    delivery_date: date
    decision_cutoff: datetime
    latest_publish_time: datetime
    earliest_publish_time: datetime
    period_count: int
    mean_mw: float
    peak_mw: float
    peak_time: datetime
    min_mw: float
    actual_mean_mw: float | None
    periods: list[LatestForecastPeriod]
