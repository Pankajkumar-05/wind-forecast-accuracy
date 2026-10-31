from datetime import date, time
from zoneinfo import ZoneInfo

from app.core.decision_rule import DecisionRule
from tests.helpers import utc

LONDON = ZoneInfo("Europe/London")


def make_rule(cutoff: time = time(9, 0), days_ahead: int = 1) -> DecisionRule:
    return DecisionRule(cutoff_time=cutoff, timezone=LONDON, days_ahead=days_ahead)


def test_cutoff_is_day_before_delivery_at_configured_time():
    # January is GMT, so London 09:00 == 09:00 UTC
    assert make_rule().cutoff_for(date(2026, 1, 15)) == utc(2026, 1, 14, 9, 0)


def test_cutoff_respects_days_ahead_setting():
    assert make_rule(days_ahead=2).cutoff_for(date(2026, 1, 15)) == utc(2026, 1, 13, 9, 0)


def test_cutoff_converts_london_summer_time_to_utc():
    # In July London is UTC+1, so 09:00 London is 08:00 UTC
    assert make_rule().cutoff_for(date(2026, 7, 15)) == utc(2026, 7, 14, 8, 0)


def test_delivery_date_uses_london_local_day():
    rule = make_rule()
    assert rule.delivery_date_of(utc(2026, 1, 10, 23, 30)) == date(2026, 1, 10)
    assert rule.delivery_date_of(utc(2026, 1, 11, 0, 0)) == date(2026, 1, 11)
    # In summer 23:30 UTC is already 00:30 the next day in London
    assert rule.delivery_date_of(utc(2026, 7, 10, 23, 30)) == date(2026, 7, 11)


def test_describe_is_human_readable():
    assert make_rule().describe() == "1 day(s) before delivery at 09:00 Europe/London"
