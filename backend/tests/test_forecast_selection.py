from datetime import date, time
from zoneinfo import ZoneInfo

from app.core.decision_rule import DecisionRule
from app.services.forecast_selection import dedupe_actuals, select_decision_forecasts
from tests.helpers import actual, forecast, utc

RULE = DecisionRule(cutoff_time=time(9, 0), timezone=ZoneInfo("Europe/London"), days_ahead=1)
WINDOW = (date(2026, 1, 2), date(2026, 2, 1))
TARGET = utc(2026, 1, 10, 12, 0)  # delivery day 10 Jan -> cutoff 9 Jan 09:00 UTC


def select(records):
    return select_decision_forecasts(records, RULE, *WINDOW)


def test_picks_latest_forecast_published_before_cutoff():
    records = [
        forecast(TARGET, utc(2026, 1, 8, 6), 100),
        forecast(TARGET, utc(2026, 1, 9, 8, 30), 300),  # latest one before cutoff -> chosen
        forecast(TARGET, utc(2026, 1, 8, 20), 200),
    ]
    result = select(records)
    assert result.selected[TARGET].generation_mw == 300


def test_never_uses_forecast_published_after_cutoff():
    records = [
        forecast(TARGET, utc(2026, 1, 9, 8), 100),
        forecast(TARGET, utc(2026, 1, 9, 9, 30), 999),  # after cutoff -> must be ignored
        forecast(TARGET, utc(2026, 1, 10, 11), 888),  # published just before delivery -> ignored
    ]
    result = select(records)
    assert result.selected[TARGET].generation_mw == 100
    assert result.published_after_cutoff_excluded == 2


def test_forecast_published_exactly_at_cutoff_is_allowed():
    result = select([forecast(TARGET, utc(2026, 1, 9, 9, 0), 123)])
    assert result.selected[TARGET].generation_mw == 123


def test_period_with_only_late_forecasts_gets_no_forecast():
    result = select([forecast(TARGET, utc(2026, 1, 9, 12), 500)])
    assert TARGET not in result.selected
    assert result.periods_with_only_late_forecasts == 1


def test_exact_duplicates_are_collapsed():
    records = [forecast(TARGET, utc(2026, 1, 9, 8), 100), forecast(TARGET, utc(2026, 1, 9, 8), 100)]
    result = select(records)
    assert result.duplicates_removed == 1
    assert len(result.selected) == 1


def test_each_target_half_hour_is_selected_independently():
    other = utc(2026, 1, 10, 12, 30)
    records = [
        forecast(TARGET, utc(2026, 1, 9, 8), 100),
        forecast(other, utc(2026, 1, 9, 7), 200),
        forecast(other, utc(2026, 1, 9, 8), 250),
    ]
    result = select(records)
    assert result.selected[TARGET].generation_mw == 100
    assert result.selected[other].generation_mw == 250


def test_delivery_days_outside_window_are_ignored():
    before = utc(2026, 1, 1, 12)  # delivery 1 Jan: decision in December -> out of scope
    after = utc(2026, 2, 2, 12)
    result = select([forecast(before, utc(2025, 12, 31, 8), 1), forecast(after, utc(2026, 2, 1, 8), 2)])
    assert result.selected == {}
    assert result.outside_window_ignored == 2


def test_cutoff_is_applied_per_delivery_day_not_globally():
    day1 = utc(2026, 1, 10, 12)
    day2 = utc(2026, 1, 11, 12)
    publish = utc(2026, 1, 9, 15)  # after cutoff for 10 Jan (9 Jan 09:00) but before cutoff for 11 Jan (10 Jan 09:00)
    result = select([forecast(day1, publish, 1), forecast(day2, publish, 2)])
    assert day1 not in result.selected
    assert result.selected[day2].generation_mw == 2


def test_dedupe_actuals_keeps_latest_published_value():
    start = utc(2026, 1, 10, 12)
    records = [actual(start, 100, utc(2026, 1, 10, 13)), actual(start, 150, utc(2026, 1, 10, 14))]
    by_start, duplicates = dedupe_actuals(records)
    assert duplicates == 1
    assert by_start[start].generation_mw == 150


def test_dedupe_actuals_without_publish_time_keeps_last_seen():
    start = utc(2026, 1, 10, 12)
    by_start, duplicates = dedupe_actuals([actual(start, 100), actual(start, 120)])
    assert duplicates == 1
    assert by_start[start].generation_mw == 120
