from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.decision_rule import DecisionRule
from app.services.comparison import build_comparison
from app.services.metrics import compute_metrics
from app.utils.time import expected_period_starts
from tests.helpers import actual, forecast, utc

LONDON = ZoneInfo("Europe/London")
RULE = DecisionRule(cutoff_time=time(9, 0), timezone=LONDON, days_ahead=1)
DAY = date(2026, 1, 10)
PUBLISHED = utc(2026, 1, 9, 8)  # before the D-1 09:00 cutoff for 10 Jan


def run(forecasts, actuals, start=DAY, end=DAY, resolution=60):
    return build_comparison(
        {f.start_time: f for f in forecasts},
        {a.start_time: a for a in actuals},
        RULE,
        start,
        end,
        mape_min_actual_mw=50.0,
        forecast_resolution_minutes=resolution,
    )


def hourly_forecasts(day=DAY, mw=1200.0):
    return [forecast(utc(day.year, day.month, day.day, hour), PUBLISHED, mw) for hour in range(24)]


def half_hourly_actuals(day=DAY, mw=1000.0):
    return [actual(utc(day.year, day.month, day.day, hour, minute), mw) for hour in range(24) for minute in (0, 30)]


# ---------------------------------------------------------------- exact matching and errors


def test_matches_on_start_time_and_computes_signed_error():
    t = utc(2026, 1, 10, 12)
    points, coverage = run([forecast(t, PUBLISHED, 1200)], [actual(t, 1000)])
    assert len(points) == 1
    p = points[0]
    assert p.error_mw == 200  # forecast - actual
    assert p.abs_error_mw == 200
    assert p.pct_error == pytest.approx(20.0)
    assert coverage.matched_periods == 1


def test_under_forecast_has_negative_signed_error_and_positive_abs_error():
    t = utc(2026, 1, 10, 12)
    points, _ = run([forecast(t, PUBLISHED, 800)], [actual(t, 1000)])
    assert points[0].error_mw == -200
    assert points[0].abs_error_mw == 200


def test_lead_time_is_hours_between_publish_and_delivery():
    t = utc(2026, 1, 10, 12)
    points, _ = run([forecast(t, PUBLISHED, 1)], [actual(t, 1)])
    assert points[0].lead_time_hours == pytest.approx(28.0)


def test_zero_actual_is_matched_but_percentage_is_none():
    t = utc(2026, 1, 10, 12)
    points, _ = run([forecast(t, PUBLISHED, 300)], [actual(t, 0)])
    assert points[0].error_mw == 300
    assert points[0].pct_error is None


def test_mismatched_timestamps_do_not_match():
    points, coverage = run([forecast(utc(2026, 1, 10, 12, 0), PUBLISHED, 1)], [actual(utc(2026, 1, 10, 12, 30), 1)])
    assert points == []
    assert coverage.matched_periods == 0


def test_periods_outside_requested_range_are_excluded():
    inside, outside = utc(2026, 1, 10, 12), utc(2026, 1, 11, 12)
    points, coverage = run(
        [forecast(inside, PUBLISHED, 1), forecast(outside, PUBLISHED, 1)], [actual(inside, 1), actual(outside, 1)]
    )
    assert [p.start_time for p in points] == [inside]
    assert coverage.expected_forecast_periods == 24


# ---------------------------------------------------------------- hourly WINDFOR vs half-hourly FUELHH


def test_hourly_forecasts_pair_only_at_the_hour_and_never_fill_the_half_hour():
    forecasts = [forecast(utc(2026, 1, 10, 12), PUBLISHED, 1200), forecast(utc(2026, 1, 10, 13), PUBLISHED, 1300)]
    actuals = [
        actual(utc(2026, 1, 10, 12, 0), 1000),
        actual(utc(2026, 1, 10, 12, 30), 5000),  # no forecast at 12:30: must NOT be paired with the 12:00 forecast
        actual(utc(2026, 1, 10, 13, 0), 1000),
        actual(utc(2026, 1, 10, 13, 30), 5000),
    ]
    points, coverage = run(forecasts, actuals)
    assert [p.start_time for p in points] == [utc(2026, 1, 10, 12), utc(2026, 1, 10, 13)]
    assert all(p.start_time.minute == 0 for p in points)
    assert [p.forecast_mw for p in points] == [1200, 1300]  # values exactly as published: not repeated or blended
    assert [p.actual_mw for p in points] == [1000, 1000]  # the 5000 MW :30 actuals were not averaged in
    assert [p.error_mw for p in points] == [200, 300]
    assert coverage.actual_periods_total == 4
    assert coverage.actual_periods_off_forecast_grid == 2


def test_half_hour_actuals_are_not_counted_as_missing_forecasts():
    forecasts = [forecast(utc(2026, 1, 10, 12), PUBLISHED, 1), forecast(utc(2026, 1, 10, 13), PUBLISHED, 1)]
    actuals = half_hourly_actuals()
    _, coverage = run(forecasts, actuals)
    # Only hourly grid periods without a forecast are "missing": 24 expected - 2 present = 22.
    assert coverage.expected_forecast_periods == 24
    assert coverage.missing_forecast_periods == 22
    assert coverage.actual_periods_off_forecast_grid == 24  # the 24 :30 periods, reported separately


def test_full_hourly_day_has_complete_forecast_grid_coverage():
    points, coverage = run(hourly_forecasts(), half_hourly_actuals())
    assert len(points) == 24
    assert coverage.expected_forecast_periods == 24
    assert coverage.forecast_periods == 24
    assert coverage.actual_periods_on_forecast_grid == 24
    assert coverage.matched_periods == 24
    assert coverage.missing_forecast_periods == 0
    assert coverage.missing_actual_periods == 0
    assert coverage.forecast_periods_off_grid == 0
    assert coverage.actual_periods_total == 48
    assert coverage.actual_periods_off_forecast_grid == 24
    assert coverage.forecast_resolution_minutes == 60


def test_a_real_forecast_gap_is_still_reported_as_missing():
    forecasts = [f for f in hourly_forecasts() if f.start_time != utc(2026, 1, 10, 5)]
    points, coverage = run(forecasts, half_hourly_actuals())
    assert len(points) == 23
    assert coverage.missing_forecast_periods == 1  # the 05:00 forecast; NOT the 24 :30 periods
    assert coverage.actual_periods_off_forecast_grid == 24


def test_a_real_actual_gap_is_still_reported_as_missing():
    actuals = [a for a in half_hourly_actuals() if a.start_time != utc(2026, 1, 10, 7)]
    points, coverage = run(hourly_forecasts(), actuals)
    assert len(points) == 23
    assert coverage.missing_actual_periods == 1


def test_forecast_off_the_expected_grid_is_still_matched_exactly_and_counted():
    t = utc(2026, 1, 10, 12, 30)  # a :30 forecast although the grid is hourly
    points, coverage = run([forecast(t, PUBLISHED, 900)], [actual(t, 1000)])
    assert [p.start_time for p in points] == [t]
    assert coverage.forecast_periods_off_grid == 1


def test_half_hourly_resolution_setting_still_works():
    forecasts = [forecast(a.start_time, PUBLISHED, 1100) for a in half_hourly_actuals()]
    points, coverage = run(forecasts, half_hourly_actuals(), resolution=30)
    assert len(points) == 48
    assert coverage.expected_forecast_periods == 48
    assert coverage.actual_periods_off_forecast_grid == 0


def test_half_hour_actual_values_never_change_the_metrics():
    base_points, _ = run(hourly_forecasts(), half_hourly_actuals())
    # Same hourly actuals, but wildly different (and zero) values at :30.
    changed = [actual(a.start_time, 123456.0 if a.start_time.minute == 30 else a.generation_mw) for a in half_hourly_actuals()]
    changed[1] = actual(changed[1].start_time, 0.0)  # a zero at 00:30
    changed_points, _ = run(hourly_forecasts(), changed)
    assert compute_metrics(base_points) == compute_metrics(changed_points)
    assert compute_metrics(changed_points).mape_excluded == 0  # the zero at :30 is not a matched pair


# ---------------------------------------------------------------- expected forecast grid


def test_expected_forecast_periods_for_multi_day_range():
    _, coverage = run([], [], start=date(2026, 1, 10), end=date(2026, 1, 12))
    assert coverage.expected_forecast_periods == 3 * 24


def test_expected_grid_handles_clock_change_days():
    spring, autumn = date(2026, 3, 29), date(2026, 10, 25)  # UK clocks forward / back
    assert len(expected_period_starts(spring, spring, LONDON, timedelta(hours=1))) == 23
    assert len(expected_period_starts(autumn, autumn, LONDON, timedelta(hours=1))) == 25
    # the default step is still the 30-minute FUELHH grid
    assert len(expected_period_starts(spring, spring, LONDON)) == 46


def test_forecast_grid_is_whole_hours_in_utc():
    grid = expected_period_starts(DAY, DAY, LONDON, timedelta(hours=1))
    assert {t.minute for t in grid} == {0}
