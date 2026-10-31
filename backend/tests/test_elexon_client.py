from datetime import date, datetime, timezone

import pytest

from app.core.errors import ElexonResponseError, ElexonUpstreamError
from app.utils.time import date_chunks, datetime_chunks
from tests.conftest import FakeElexon


async def test_actuals_request_filters_wind_and_uses_settlement_dates(fake_elexon, client_factory):
    client = client_factory(fake_elexon)
    await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 11))
    request = fake_elexon.requests[0]
    assert request.url.path.endswith("/datasets/FUELHH/stream")
    assert request.url.params["fuelType"] == "WIND"
    assert request.url.params["settlementDateFrom"] == "2026-01-10"
    assert request.url.params["settlementDateTo"] == "2026-01-11"


async def test_forecast_request_uses_publish_time_range(fake_elexon, client_factory):
    client = client_factory(fake_elexon)
    start = datetime(2026, 1, 9, tzinfo=timezone.utc)
    end = datetime(2026, 1, 10, 9, tzinfo=timezone.utc)
    await client.fetch_wind_forecast_rows(start, end)
    params = fake_elexon.requests[0].url.params
    assert fake_elexon.requests[0].url.path.endswith("/datasets/WINDFOR/stream")
    assert params["publishDateTimeFrom"] == "2026-01-09T00:00:00Z"
    assert params["publishDateTimeTo"] == "2026-01-10T09:00:00Z"


async def test_long_ranges_are_split_into_chunks(fake_elexon, client_factory):
    client = client_factory(fake_elexon, request_chunk_days=3)
    await client.fetch_actual_wind_rows(date(2026, 1, 1), date(2026, 1, 10))
    assert len(fake_elexon.requests) == 4  # 3 + 3 + 3 + 1 days


async def test_transient_errors_are_retried_then_succeed(fake_elexon, client_factory):
    fake_elexon.fail_with = 503
    fake_elexon.fail_times = 2
    client = client_factory(fake_elexon, request_max_retries=3)
    rows = await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))
    assert rows  # eventually succeeded
    assert len(fake_elexon.requests) == 3


async def test_persistent_failure_raises_instead_of_returning_partial_data(fake_elexon, client_factory):
    fake_elexon.fail_with = 500
    fake_elexon.fail_times = -1
    client = client_factory(fake_elexon, request_max_retries=2)
    with pytest.raises(ElexonUpstreamError):
        await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))
    assert len(fake_elexon.requests) == 3  # 1 attempt + 2 retries


async def test_client_errors_are_not_retried(fake_elexon, client_factory):
    fake_elexon.fail_with = 400
    fake_elexon.fail_times = -1
    client = client_factory(fake_elexon)
    with pytest.raises(ElexonUpstreamError):
        await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))
    assert len(fake_elexon.requests) == 1


async def test_non_json_body_raises_response_error(fake_elexon, client_factory):
    fake_elexon.raw_body = "<html>maintenance</html>"
    client = client_factory(fake_elexon)
    with pytest.raises(ElexonResponseError):
        await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))


async def test_unexpected_json_shape_raises_response_error(fake_elexon, client_factory):
    fake_elexon.raw_body = '"just a string"'
    client = client_factory(fake_elexon)
    with pytest.raises(ElexonResponseError):
        await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))


async def test_data_envelope_is_accepted(fake_elexon, client_factory):
    fake_elexon.raw_body = '{"data": [{"fuelType": "WIND"}]}'
    client = client_factory(fake_elexon)
    rows = await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))
    assert rows == [{"fuelType": "WIND"}]


async def test_empty_response_returns_no_rows(client_factory):
    client = client_factory(FakeElexon([], []))
    assert await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10)) == []


async def test_historical_chunks_are_served_from_disk_cache(fake_elexon, client_factory, tmp_path):
    client = client_factory(fake_elexon, cache_dir=str(tmp_path))
    await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))
    await client.fetch_actual_wind_rows(date(2026, 1, 10), date(2026, 1, 10))
    assert len(fake_elexon.requests) == 1


def test_date_chunks_cover_range_without_gaps_or_overlap():
    chunks = date_chunks(date(2026, 1, 1), date(2026, 1, 8), 3)
    assert chunks == [
        (date(2026, 1, 1), date(2026, 1, 3)),
        (date(2026, 1, 4), date(2026, 1, 6)),
        (date(2026, 1, 7), date(2026, 1, 8)),
    ]


def test_datetime_chunks_are_contiguous():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 8, 9, tzinfo=timezone.utc)
    chunks = datetime_chunks(start, end, 3)
    assert chunks[0][0] == start and chunks[-1][1] == end
    assert all(a[1] == b[0] for a, b in zip(chunks, chunks[1:]))
