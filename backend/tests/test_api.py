import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import FakeElexon, build_fake_rows, make_settings


def test_health_does_not_call_elexon(api, fake_elexon):
    response = api.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert fake_elexon.requests == []


def test_config_exposes_decision_rule(api):
    body = api.get("/api/config").json()
    assert body["decision_rule"]["cutoff_time"] == "09:00"
    assert body["decision_rule"]["timezone"] == "Europe/London"
    assert body["window_start"] == "2026-01-10"


def test_comparison_uses_decision_time_forecast_not_the_late_one(api):
    body = api.get("/api/comparison").json()
    assert len(body["points"]) == 48  # 2 days x 24 hourly forecast periods
    first = body["points"][0]
    assert first["forecast_mw"] == 1100.0  # NOT the 9999 published after the cutoff
    assert first["actual_mw"] == 1000.0
    assert first["error_mw"] == 100.0
    assert first["abs_error_mw"] == 100.0
    assert first["pct_error"] == pytest.approx(10.0)


def test_metrics_values_and_data_quality(api):
    body = api.get("/api/metrics").json()
    overall = body["overall"]
    assert overall["n"] == 48
    assert overall["mae"] == pytest.approx(100.0)
    assert overall["rmse"] == pytest.approx(100.0)
    assert overall["bias"] == pytest.approx(100.0)
    assert overall["mape"] == pytest.approx(10.0)
    assert len(body["daily"]) == 2
    coverage = body["quality"]["coverage"]
    assert coverage["matched_periods"] == 48
    assert coverage["expected_forecast_periods"] == 48
    assert coverage["missing_forecast_periods"] == 0
    # We only fetch forecasts published up to the last cutoff, so just the 24 late forecasts for
    # 10 Jan (published 9 Jan 12:00) were seen and excluded; those for 11 Jan are never requested.
    assert body["quality"]["forecasts_published_after_cutoff_excluded"] == 24


def test_date_filter_narrows_results(api):
    body = api.get("/api/comparison", params={"start": "2026-01-11", "end": "2026-01-11"}).json()
    assert len(body["points"]) == 24
    assert {p["delivery_date"] for p in body["points"]} == {"2026-01-11"}


def test_elexon_is_fetched_once_and_cached_across_endpoints(api, fake_elexon):
    api.get("/api/comparison")
    requests_after_first_call = len(fake_elexon.requests)
    assert requests_after_first_call >= 2  # at least one FUELHH call and one WINDFOR call
    api.get("/api/metrics")
    api.get("/api/forecasts")
    api.get("/api/actuals")
    api.get("/api/forecasts/latest")
    assert len(fake_elexon.requests) == requests_after_first_call  # everything else came from the cache


def test_actuals_endpoint_returns_only_wind(api):
    body = api.get("/api/actuals").json()
    assert len(body["actuals"]) == 96
    assert all(a["actual_mw"] == 1000.0 for a in body["actuals"])


def test_forecasts_endpoint_returns_decision_time_forecasts_with_lead_time(api):
    body = api.get("/api/forecasts").json()
    assert len(body["forecasts"]) == 48
    assert body["forecasts"][0]["forecast_mw"] == 1100.0
    assert body["forecasts"][0]["lead_time_hours"] > 0


def test_latest_forecast_defaults_to_last_delivery_day(api):
    body = api.get("/api/forecasts/latest").json()
    assert body["delivery_date"] == "2026-01-11"
    assert body["decision_cutoff"] == "2026-01-10T09:00:00Z"
    assert body["period_count"] == 24
    assert body["mean_mw"] == 1100.0
    assert body["latest_publish_time"] == "2026-01-10T08:00:00Z"
    assert body["actual_mean_mw"] == 1000.0


def test_latest_forecast_for_specific_day(api):
    body = api.get("/api/forecasts/latest", params={"delivery_date": "2026-01-10"}).json()
    assert body["delivery_date"] == "2026-01-10"


def test_latest_forecast_unknown_day_is_404(api):
    response = api.get("/api/forecasts/latest", params={"delivery_date": "2026-01-20"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"start": "2026-01-11", "end": "2026-01-10"},  # start after end
        {"start": "2025-12-01"},  # before the supported window
        {"end": "2026-03-01"},  # after the supported window
    ],
)
def test_invalid_ranges_return_422(api, params):
    response = api.get("/api/comparison", params=params)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_malformed_date_returns_422(api):
    assert api.get("/api/metrics", params={"start": "not-a-date"}).status_code == 422


def test_elexon_outage_returns_502_with_friendly_message(fake_elexon, settings, client_factory):
    fake_elexon.fail_with = 503
    fake_elexon.fail_times = -1
    app = create_app(settings, client_factory(fake_elexon))
    with TestClient(app) as client:
        response = client.get("/api/comparison")
    assert response.status_code == 502
    assert "unavailable" in response.json()["detail"].lower()


def test_failed_load_is_not_cached_and_recovers(fake_elexon, settings, client_factory):
    fake_elexon.fail_with = 503
    fake_elexon.fail_times = -1
    app = create_app(settings, client_factory(fake_elexon))
    with TestClient(app) as client:
        assert client.get("/api/comparison").status_code == 502
        fake_elexon.fail_with = None  # Elexon recovers
        assert client.get("/api/comparison").status_code == 200


def test_empty_elexon_response_gives_empty_but_honest_result(settings, client_factory):
    app = create_app(settings, client_factory(FakeElexon([], [])))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
        assert body["overall"]["n"] == 0
        assert body["overall"]["mae"] is None
        assert any("No forecast periods" in w for w in body["quality"]["warnings"])
        assert client.get("/api/forecasts/latest").status_code == 404


def test_missing_actuals_are_surfaced_in_warnings(settings, client_factory):
    actuals, forecasts = build_fake_rows()
    partial_actuals = actuals[:20]  # only the first few periods have actuals
    app = create_app(settings, client_factory(FakeElexon(partial_actuals, forecasts)))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
    assert body["overall"]["n"] < 48
    assert body["quality"]["coverage"]["missing_actual_periods"] > 0
    assert any("no actual" in w for w in body["quality"]["warnings"])


def test_zero_actual_does_not_break_metrics(settings, client_factory):
    actuals, forecasts = build_fake_rows(actual_mw=0.0)
    app = create_app(settings, client_factory(FakeElexon(actuals, forecasts)))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
    assert body["overall"]["mae"] == pytest.approx(1100.0)
    assert body["overall"]["mape"] is None
    assert body["overall"]["mape_excluded"] == 48


def test_duplicate_rows_from_elexon_are_handled(settings, client_factory):
    actuals, forecasts = build_fake_rows()
    app = create_app(settings, client_factory(FakeElexon(actuals + actuals, forecasts + forecasts)))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
    assert body["overall"]["n"] == 48
    assert body["quality"]["duplicates_removed"] > 0


def test_malformed_rows_are_skipped_and_reported(settings, client_factory):
    actuals, forecasts = build_fake_rows()
    actuals.append({"fuelType": "WIND", "startTime": "garbage", "generation": 5})
    forecasts.append({"startTime": "2026-01-10T12:00:00Z", "publishTime": "2026-01-09T08:00:00Z", "generation": None})
    app = create_app(settings, client_factory(FakeElexon(actuals, forecasts)))
    with TestClient(app) as client:
        body = client.get("/api/metrics").json()
    assert body["overall"]["n"] == 48
    assert body["quality"]["malformed_rows_skipped"] == 2


def test_decision_cutoff_is_configurable(settings, client_factory):
    """Moving the cutoff to 13:00 makes the 12:00 'late' forecast (9999) the decision-time one."""
    actuals, forecasts = build_fake_rows()
    s = make_settings(decision_cutoff_time="13:00")
    app = create_app(s, client_factory(FakeElexon(actuals, forecasts), decision_cutoff_time="13:00"))
    with TestClient(app) as client:
        body = client.get("/api/comparison").json()
    assert body["points"][0]["forecast_mw"] == 9999.0
