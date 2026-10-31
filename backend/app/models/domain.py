"""Plain, immutable domain objects used by the processing layer (no I/O, no framework)."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class ForecastRecord:
    """One WINDFOR row: a forecast for ``start_time`` created at ``publish_time``."""

    start_time: datetime
    publish_time: datetime
    generation_mw: float


@dataclass(frozen=True)
class ActualRecord:
    """One FUELHH row for fuelType WIND: what was actually generated in a 30-minute period."""

    start_time: datetime
    generation_mw: float
    publish_time: datetime | None = None


@dataclass(frozen=True)
class ComparisonPoint:
    """A forecast period for which a decision-time forecast and an actual exist at exactly the same startTime."""

    start_time: datetime
    delivery_date: date
    forecast_mw: float
    actual_mw: float
    forecast_publish_time: datetime
    lead_time_hours: float
    error_mw: float  # signed: forecast - actual (positive = over-forecast)
    abs_error_mw: float
    pct_error: float | None  # signed % of actual; None when actual is below the MAPE floor


@dataclass(frozen=True)
class Coverage:
    """How complete the data is for the requested range. Shown to users, never hidden.

    Coverage is measured on the FORECAST grid (WINDFOR publishes hourly targets). FUELHH actuals
    are every 30 minutes, so actual periods that fall between forecast targets (the :30 periods)
    have no forecast by design: they are counted separately and are not a data gap.
    """

    forecast_resolution_minutes: int
    expected_forecast_periods: int  # forecast-grid periods in the range (e.g. 744 hourly periods in 31 days)
    forecast_periods: int  # of those, periods with a decision-time forecast
    actual_periods_on_forecast_grid: int  # of those, periods with an actual
    matched_periods: int  # pairs evaluated (exact startTime match)
    missing_forecast_periods: int  # forecast-grid periods WITHOUT a decision-time forecast (a real gap)
    missing_actual_periods: int  # forecast-grid periods WITHOUT an actual (a real gap)
    forecast_periods_off_grid: int  # forecast timestamps not on the expected grid (normally 0)
    actual_periods_total: int  # all FUELHH periods in the range (30-minute resolution)
    actual_periods_off_forecast_grid: int  # actual periods with no forecast target by resolution (the :30 periods)
