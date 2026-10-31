"""API-level behaviour for the live-verified data shape: hourly WINDFOR targets, half-hourly FUELHH."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeElexon, build_fake_rows, make_settings


def test_config_exposes_the_forecast_resolution(api):
    assert api.get("/api/config").json()["forecast_resolution_minutes"] == 60


def test_coverage_is_reported_on_the_forecast_grid_not_as_50_percent_missing(api):
    quality = api.get("/api/metrics").json()["quality"]
    coverage = quality["coverage"]
    assert coverage["expected_forecast_periods"] == 48  # 2 days x 24 hourly periods
    assert coverage["matched_periods"] == 48
    assert coverage["missing_forecast_periods"] == 0
    assert coverage["missing_actual_periods"] == 0
    assert coverage["actual_periods_total"] == 96  # FUELHH is every 30 minutes
    assert coverage["actual_periods_off_forecast_grid"] == 48  # the :30 periods: no forecast by resolution
    assert coverage["forecast_resolution_minutes"] == 60
    # The :30 actuals are information, not a data problem: no warning, no "partial data".
    assert quality["warnings"] == []


def test_every_compared_point_is_on_the_hour(api):
    points = api.get("/api/comparison").json()["points"]
    assert len(points) == 48
    assert all(p["start_time"].endswith(":00:00Z") for p in points)


def test_metrics_ignore_the_half_hour_actuals_entirely(settings, client_factory):
    """Rule: only exact timestamp matches count. Absurd :30 actuals must not move any metric."""
    actuals, forecasts = build_fake_rows()
    baseline = _metrics_for(settings, client_factory, actuals, forecasts)

    tampered = [dict(r) for r in actuals]
    for row in tampered:
        if row["fuelType"] == "WIND" and row["startTime"].endswith(":30:00Z"):
            row["generation"] = 0.0 if row["startTime"] < "2026-01-10T12" else 987654.0
    changed = _metrics_for(settings, client_factory, tampered, forecasts)

    assert changed["overall"] == baseline["overall"]
    assert changed["daily"] == baseline["daily"]
    assert changed["overall"]["mape_excluded"] == 0


def test_hourly_forecast_is_never_copied_into_half_hour_periods(api):
    forecasts = api.get("/api/forecasts").json()["forecasts"]
    assert len(forecasts) == 48  # 24 per day: exactly the hourly rows WINDFOR returned
    assert all(f["start_time"].endswith(":00:00Z") for f in forecasts)


def test_off_grid_forecasts_are_evaluated_and_warned_about(settings, client_factory):
    """If WINDFOR ever becomes half-hourly while the setting still says hourly, say so loudly."""
    actuals, forecasts = build_fake_rows(forecast_step_minutes=30)
    app = create_app(settings, client_factory(FakeElexon(actuals, forecasts)))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
    assert body["overall"]["n"] == 96  # still evaluated by exact startTime match
    assert body["quality"]["coverage"]["forecast_periods_off_grid"] == 48
    assert any("not on the expected 60-minute grid" in w for w in body["quality"]["warnings"])


def test_half_hourly_resolution_setting_gives_full_half_hourly_coverage(client_factory):
    s = make_settings(forecast_resolution_minutes=30)
    actuals, forecasts = build_fake_rows(forecast_step_minutes=30)
    app = create_app(s, client_factory(FakeElexon(actuals, forecasts), forecast_resolution_minutes=30))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
    coverage = body["quality"]["coverage"]
    assert coverage["expected_forecast_periods"] == 96
    assert coverage["matched_periods"] == 96
    assert coverage["actual_periods_off_forecast_grid"] == 0
    assert body["quality"]["warnings"] == []


def test_a_missing_hourly_forecast_is_a_real_gap_and_warns(settings, client_factory):
    actuals, forecasts = build_fake_rows()
    # Drop every forecast row for the 05:00 target on 10 Jan.
    forecasts = [r for r in forecasts if r["startTime"] != "2026-01-10T05:00:00Z"]
    app = create_app(settings, client_factory(FakeElexon(actuals, forecasts)))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
    assert body["quality"]["coverage"]["missing_forecast_periods"] == 1
    assert body["overall"]["n"] == 47
    assert any("1 of 48 expected forecast periods" in w for w in body["quality"]["warnings"])


def _metrics_for(settings, client_factory, actuals, forecasts):
    app = create_app(settings, client_factory(FakeElexon(actuals, forecasts)))
    with TestClient(app) as client:
        response = client.get("/api/metrics")
    assert response.status_code == 200
    return response.json()
