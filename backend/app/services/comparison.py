"""Match decision-time forecasts with actuals and compute per-period errors.

Matching rule (deliberately strict): a forecast and an actual form a pair ONLY when their
``startTime`` is exactly equal. Nothing is interpolated, forward-filled, duplicated or averaged.
WINDFOR targets are hourly (on the hour) while FUELHH actuals are every 30 minutes, so the
actual periods at :30 simply have no forecast to compare with. They are reported separately and
are not a data gap.
"""

from datetime import date, datetime, timedelta

from app.core.decision_rule import DecisionRule
from app.models.domain import ActualRecord, ComparisonPoint, Coverage, ForecastRecord
from app.services.metrics import percentage_error
from app.utils.time import expected_period_starts, range_bounds_utc


def build_comparison(
    forecasts: dict[datetime, ForecastRecord],
    actuals: dict[datetime, ActualRecord],
    rule: DecisionRule,
    range_start: date,
    range_end: date,
    mape_min_actual_mw: float,
    *,
    forecast_resolution_minutes: int,
) -> tuple[list[ComparisonPoint], Coverage]:
    """Inner-join forecasts and actuals on exactly equal ``startTime`` for local delivery days in range.

    The evaluated pairs are decided by the data: every forecast timestamp that WINDFOR actually
    returned (inside the range) is compared with the actual at the same timestamp, if there is one.

    ``forecast_resolution_minutes`` only defines the EXPECTED forecast grid, which is the
    denominator for coverage. Periods missing on either side are NOT dropped silently: they are
    counted in ``Coverage`` so the UI can show how complete the evaluation is.
    """
    lower, upper = range_bounds_utc(range_start, range_end, rule.timezone)
    forecast_in_range = {start for start in forecasts if lower <= start < upper}
    actual_in_range = {start for start in actuals if lower <= start < upper}
    forecast_grid = set(
        expected_period_starts(range_start, range_end, rule.timezone, timedelta(minutes=forecast_resolution_minutes))
    )

    points: list[ComparisonPoint] = []
    for start in sorted(forecast_in_range & actual_in_range):
        forecast = forecasts[start]
        actual = actuals[start]
        error = forecast.generation_mw - actual.generation_mw
        points.append(
            ComparisonPoint(
                start_time=start,
                delivery_date=rule.delivery_date_of(start),
                forecast_mw=forecast.generation_mw,
                actual_mw=actual.generation_mw,
                forecast_publish_time=forecast.publish_time,
                lead_time_hours=(start - forecast.publish_time).total_seconds() / 3600.0,
                error_mw=error,
                abs_error_mw=abs(error),
                pct_error=percentage_error(error, actual.generation_mw, mape_min_actual_mw),
            )
        )

    coverage = Coverage(
        forecast_resolution_minutes=forecast_resolution_minutes,
        expected_forecast_periods=len(forecast_grid),
        forecast_periods=len(forecast_grid & forecast_in_range),
        actual_periods_on_forecast_grid=len(forecast_grid & actual_in_range),
        matched_periods=len(points),
        missing_forecast_periods=len(forecast_grid - forecast_in_range),
        missing_actual_periods=len(forecast_grid - actual_in_range),
        forecast_periods_off_grid=len(forecast_in_range - forecast_grid),
        actual_periods_total=len(actual_in_range),
        actual_periods_off_forecast_grid=len(actual_in_range - forecast_grid),
    )
    return points, coverage
