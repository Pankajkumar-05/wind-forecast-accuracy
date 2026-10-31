import math
from datetime import date

import pytest

from app.models.domain import ComparisonPoint
from app.services.metrics import compute_daily_metrics, compute_metrics, percentage_error, percentile
from tests.helpers import utc


def point(forecast_mw: float, actual_mw: float, day: int = 10, minute_offset: int = 0, min_actual: float = 50.0):
    error = forecast_mw - actual_mw
    return ComparisonPoint(
        start_time=utc(2026, 1, day, 12, minute_offset),
        delivery_date=date(2026, 1, day),
        forecast_mw=forecast_mw,
        actual_mw=actual_mw,
        forecast_publish_time=utc(2026, 1, day - 1, 8),
        lead_time_hours=28.0,
        error_mw=error,
        abs_error_mw=abs(error),
        pct_error=percentage_error(error, actual_mw, min_actual),
    )


def test_mae_rmse_bias_on_known_values():
    # errors: +100, -200, +300  ->  MAE 200, bias 66.67, RMSE sqrt((1e4+4e4+9e4)/3)
    points = [point(1100, 1000, minute_offset=0), point(800, 1000, minute_offset=30), point(1300, 1000, minute_offset=0, day=11)]
    m = compute_metrics(points)
    assert m.n == 3
    assert m.mae == pytest.approx(200.0)
    assert m.bias == pytest.approx(200.0 / 3)
    assert m.rmse == pytest.approx(math.sqrt(140000 / 3))


def test_rmse_is_never_smaller_than_mae():
    m = compute_metrics([point(1100, 1000), point(1500, 1000, minute_offset=30), point(900, 1000, day=11)])
    assert m.rmse >= m.mae


def test_bias_sign_positive_means_over_forecast():
    m = compute_metrics([point(1200, 1000), point(1300, 1000, minute_offset=30)])
    assert m.bias > 0


def test_opposite_errors_cancel_in_bias_but_not_in_mae():
    m = compute_metrics([point(1100, 1000), point(900, 1000, minute_offset=30)])
    assert m.bias == pytest.approx(0.0)
    assert m.mae == pytest.approx(100.0)


def test_empty_input_returns_none_not_zero():
    m = compute_metrics([])
    assert m.n == 0
    assert m.mae is None and m.rmse is None and m.bias is None and m.mape is None


def test_percentage_error_zero_actual_is_none():
    assert percentage_error(100.0, 0.0, 50.0) is None


def test_percentage_error_below_floor_is_none():
    assert percentage_error(10.0, 49.9, 50.0) is None


def test_percentage_error_at_floor_is_computed():
    assert percentage_error(10.0, 50.0, 50.0) == pytest.approx(20.0)


def test_percentage_error_is_signed():
    assert percentage_error(-100.0, 1000.0, 50.0) == pytest.approx(-10.0)


def test_mape_excludes_near_zero_actuals_and_reports_count():
    points = [point(1100, 1000), point(900, 1000, minute_offset=30), point(80, 0, day=11)]  # last: actual 0
    m = compute_metrics(points)
    assert m.mape == pytest.approx(10.0)
    assert m.mape_n == 2
    assert m.mape_excluded == 1


def test_mape_is_none_when_every_actual_is_zero():
    m = compute_metrics([point(10, 0), point(20, 0, minute_offset=30)])
    assert m.mape is None
    assert m.mape_n == 0
    assert m.mae == pytest.approx(15.0)  # MAE is still valid


def test_mae_percent_of_mean_actual():
    m = compute_metrics([point(1100, 1000), point(1900, 2000, minute_offset=30)])
    assert m.mae == pytest.approx(100.0)
    assert m.mae_pct_of_mean_actual == pytest.approx(100.0 / 1500.0 * 100.0)


def test_percentile_linear_interpolation():
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert percentile([10], 90) == 10
    assert percentile([0, 100], 90) == pytest.approx(90.0)


def test_daily_metrics_group_by_delivery_day():
    points = [point(1100, 1000, day=10), point(900, 1000, day=10, minute_offset=30), point(1500, 1000, day=11)]
    daily = compute_daily_metrics(points)
    assert [d.delivery_date for d in daily] == [date(2026, 1, 10), date(2026, 1, 11)]
    assert daily[0].mae == pytest.approx(100.0)
    assert daily[0].bias == pytest.approx(0.0)
    assert daily[1].mae == pytest.approx(500.0)
    assert daily[1].n == 1
