import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_forecast_resolution_defaults_to_hourly_as_verified_on_live_data():
    assert Settings(_env_file=None).forecast_resolution_minutes == 60


@pytest.mark.parametrize("minutes", [30, 60, 90, 120])
def test_valid_forecast_resolutions(minutes):
    assert Settings(forecast_resolution_minutes=minutes, _env_file=None).forecast_resolution_minutes == minutes


@pytest.mark.parametrize("minutes", [0, -30, 15, 45, 59])
def test_invalid_forecast_resolutions_are_rejected(minutes):
    with pytest.raises(ValidationError):
        Settings(forecast_resolution_minutes=minutes, _env_file=None)


def test_decision_rule_and_window_defaults_are_unchanged():
    s = Settings(_env_file=None)
    assert s.decision_cutoff_time == "09:00"
    assert s.decision_timezone == "Europe/London"
    assert s.decision_days_ahead == 1
    assert (s.delivery_window_start.isoformat(), s.delivery_window_end.isoformat()) == ("2026-01-02", "2026-02-01")
