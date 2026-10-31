"""Forecast-accuracy metrics. Pure functions, no I/O.

Sign convention everywhere: error = forecast - actual
    positive  -> forecast was too HIGH (over-forecast: buyer under-buys other power)
    negative  -> forecast was too LOW  (under-forecast: buyer over-buys)
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.models.domain import ComparisonPoint


@dataclass(frozen=True)
class Metrics:
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


@dataclass(frozen=True)
class DailyMetrics:
    delivery_date: date
    n: int
    mae: float
    bias: float
    rmse: float


def percentage_error(error: float, actual: float, min_actual_mw: float) -> float | None:
    """Signed percentage error relative to actual, or None if actual is too small.

    Wind output can be (near) zero, where a percentage is meaningless or infinite. Below
    ``min_actual_mw`` we return None instead of dividing, and MAPE excludes the period.
    """
    if abs(actual) < min_actual_mw or actual == 0:
        return None
    return error / actual * 100.0


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile (same definition as numpy's default). q in [0, 100]."""
    if not values:
        raise ValueError("percentile of empty list")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def compute_metrics(points: list[ComparisonPoint]) -> Metrics:
    """Aggregate accuracy metrics over exactly matched forecast periods. Empty input gives Nones, not zeros."""
    n = len(points)
    if n == 0:
        return Metrics(0, None, None, None, None, 0, 0, None, None, None, None, None)

    errors = [p.error_mw for p in points]
    abs_errors = [p.abs_error_mw for p in points]
    mae = sum(abs_errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    bias = sum(errors) / n
    mean_actual = sum(p.actual_mw for p in points) / n
    mean_forecast = sum(p.forecast_mw for p in points) / n

    pct_values = [abs(p.pct_error) for p in points if p.pct_error is not None]
    mape = sum(pct_values) / len(pct_values) if pct_values else None

    return Metrics(
        n=n,
        mae=mae,
        rmse=rmse,
        bias=bias,
        mape=mape,
        mape_n=len(pct_values),
        mape_excluded=n - len(pct_values),
        mean_actual=mean_actual,
        mean_forecast=mean_forecast,
        mae_pct_of_mean_actual=(mae / mean_actual * 100.0) if mean_actual > 0 else None,
        p90_abs_error=percentile(abs_errors, 90),
        max_abs_error=max(abs_errors),
    )


def compute_daily_metrics(points: list[ComparisonPoint]) -> list[DailyMetrics]:
    """Per-delivery-day MAE / bias / RMSE, for the 'how did accuracy vary day to day' view."""
    grouped: dict[date, list[ComparisonPoint]] = defaultdict(list)
    for point in points:
        grouped[point.delivery_date].append(point)

    daily: list[DailyMetrics] = []
    for delivery_date in sorted(grouped):
        day_points = grouped[delivery_date]
        n = len(day_points)
        daily.append(
            DailyMetrics(
                delivery_date=delivery_date,
                n=n,
                mae=sum(p.abs_error_mw for p in day_points) / n,
                bias=sum(p.error_mw for p in day_points) / n,
                rmse=math.sqrt(sum(p.error_mw**2 for p in day_points) / n),
            )
        )
    return daily
