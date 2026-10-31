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


PROD_ORIGIN = "https://wind-forecast-accuracy.vercel.app"


def test_production_origin_and_localhost_allowed_by_default():
    origins = Settings(_env_file=None).cors_origin_list
    assert PROD_ORIGIN in origins
    assert "http://localhost:5173" in origins


@pytest.mark.parametrize("value", ["", "https://other.example", f"{PROD_ORIGIN}/", "*"])
def test_production_origin_always_included_and_no_wildcard(value):
    origins = Settings(cors_origins=value, _env_file=None).cors_origin_list
    assert origins.count(PROD_ORIGIN) == 1
    assert "*" not in origins


def test_cors_header_returned_for_production_origin(api):
    response = api.get("/api/health", headers={"Origin": PROD_ORIGIN})
    assert response.headers["access-control-allow-origin"] == PROD_ORIGIN
    assert "access-control-allow-origin" not in api.get("/api/health", headers={"Origin": "https://evil.example"}).headers
