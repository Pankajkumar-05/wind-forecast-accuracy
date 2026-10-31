"""Shared fixtures: a fake Elexon API served through httpx.MockTransport (no network)."""

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.elexon_client import ElexonClient

BASE_URL = "https://fake-elexon.test/bmrs/api/v1"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_settings(**overrides) -> Settings:
    values = dict(
        elexon_base_url=BASE_URL,
        delivery_window_start=date(2026, 1, 10),
        delivery_window_end=date(2026, 1, 11),
        request_chunk_days=3,
        request_max_retries=2,
        request_backoff_seconds=0.0,
        cache_dir="",
        _env_file=None,
    )
    values.update(overrides)
    return Settings(**values)


def half_hours(day: date):
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return [start + timedelta(minutes=30 * i) for i in range(48)]


def build_fake_rows(
    days=(date(2026, 1, 10), date(2026, 1, 11)),
    actual_mw=1000.0,
    early_mw=1100.0,
    late_mw=9999.0,
    forecast_step_minutes=60,
):
    """FUELHH actuals every 30 minutes plus WINDFOR forecasts every ``forecast_step_minutes``.

    Live Elexon data (Jan 2026) has hourly WINDFOR targets (:00 only) and half-hourly FUELHH, so the
    default is 60. Per forecast target there is an early forecast and a LATE forecast.

    - decision-time forecast  = early_mw   (published 08:00 UTC on D-1, before the 09:00 cutoff)
    - late forecast           = late_mw    (published 12:00 UTC on D-1, after the cutoff -> must be ignored)
    """
    actuals, forecasts = [], []
    for day in days:
        for start in half_hours(day):
            actuals.append({"fuelType": "WIND", "startTime": iso(start), "generation": actual_mw})
            actuals.append({"fuelType": "NUCLEAR", "startTime": iso(start), "generation": 4000})
            day_before = datetime.combine(day - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            if (start.hour * 60 + start.minute) % forecast_step_minutes != 0:
                continue  # no forecast target at this time (e.g. the :30 periods for hourly WINDFOR)
            forecasts.append(
                {"startTime": iso(start), "publishTime": iso(day_before + timedelta(hours=8)), "generation": early_mw}
            )
            forecasts.append(
                {"startTime": iso(start), "publishTime": iso(day_before + timedelta(hours=12)), "generation": late_mw}
            )
    return actuals, forecasts


class FakeElexon:
    """Callable used as the httpx MockTransport handler. Records every request it receives."""

    def __init__(self, actuals, forecasts):
        self.actuals = actuals
        self.forecasts = forecasts
        self.requests: list[httpx.Request] = []
        self.fail_with: int | None = None
        self.fail_times = 0
        self.raw_body: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with is not None and (self.fail_times == -1 or self.fail_times > 0):
            if self.fail_times > 0:
                self.fail_times -= 1
            return httpx.Response(self.fail_with, text="boom")
        if self.raw_body is not None:
            return httpx.Response(200, text=self.raw_body)
        if request.url.path.endswith("/FUELHH/stream"):
            return httpx.Response(200, json=self.actuals)
        if request.url.path.endswith("/WINDFOR/stream"):
            # Like the real API, return only forecasts published inside the requested range.
            params = request.url.params
            lower, upper = params.get("publishDateTimeFrom"), params.get("publishDateTimeTo")
            in_range = [
                row
                for row in self.forecasts
                if not (lower and upper and isinstance(row.get("publishTime"), str))
                or lower <= row["publishTime"] <= upper
            ]
            return httpx.Response(200, json=in_range)
        return httpx.Response(404)


@pytest.fixture
def fake_elexon() -> FakeElexon:
    actuals, forecasts = build_fake_rows()
    return FakeElexon(actuals, forecasts)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def client_factory(settings):
    def _make(fake: FakeElexon, **setting_overrides) -> ElexonClient:
        s = make_settings(**setting_overrides) if setting_overrides else settings
        http = httpx.AsyncClient(base_url=s.elexon_base_url, transport=httpx.MockTransport(fake))
        return ElexonClient(s, http=http)

    return _make


@pytest.fixture
def api(fake_elexon, settings, client_factory):
    """A TestClient for the real FastAPI app wired to the fake Elexon."""
    app = create_app(settings, client_factory(fake_elexon))
    with TestClient(app) as test_client:
        yield test_client
