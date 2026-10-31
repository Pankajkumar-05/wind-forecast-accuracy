from app.services.parsing import parse_actual_rows, parse_forecast_rows


def test_actual_rows_keep_only_wind():
    rows = [
        {"fuelType": "WIND", "startTime": "2026-01-10T12:00:00Z", "generation": 5000},
        {"fuelType": "CCGT", "startTime": "2026-01-10T12:00:00Z", "generation": 9000},
        {"fuelType": "wind", "startTime": "2026-01-10T12:30:00Z", "generation": 5100},
    ]
    parsed = parse_actual_rows(rows)
    assert [r.generation_mw for r in parsed.records] == [5000, 5100]
    assert parsed.other_fuel_types_ignored == 1
    assert parsed.malformed == 0


def test_actual_rows_normalise_timestamps_to_utc():
    parsed = parse_actual_rows([{"fuelType": "WIND", "startTime": "2026-01-10T12:00:00+00:00", "generation": 1}])
    assert parsed.records[0].start_time.utcoffset().total_seconds() == 0


def test_malformed_actual_rows_are_counted_not_fatal():
    rows = [
        {"fuelType": "WIND", "startTime": "not-a-date", "generation": 1},
        {"fuelType": "WIND", "startTime": "2026-01-10T12:00:00Z", "generation": None},
        {"fuelType": "WIND", "startTime": "2026-01-10T12:00:00Z"},
        {"fuelType": "WIND", "startTime": "2026-01-10T12:00:00Z", "generation": "abc"},
        {"fuelType": "WIND", "startTime": "2026-01-10T12:00:00Z", "generation": float("nan")},
        "garbage",
        {"fuelType": "WIND", "startTime": "2026-01-10T12:00:00Z", "generation": 10},
    ]
    parsed = parse_actual_rows(rows)
    assert len(parsed.records) == 1
    assert parsed.malformed == 6


def test_zero_generation_is_valid():
    parsed = parse_actual_rows([{"fuelType": "WIND", "startTime": "2026-01-10T12:00:00Z", "generation": 0}])
    assert parsed.records[0].generation_mw == 0
    assert parsed.malformed == 0


def test_forecast_rows_parse_publish_time():
    rows = [{"startTime": "2026-01-10T12:00:00Z", "publishTime": "2026-01-09T08:00:00Z", "generation": 4321.5}]
    parsed = parse_forecast_rows(rows)
    assert parsed.records[0].generation_mw == 4321.5
    assert parsed.records[0].publish_time.isoformat() == "2026-01-09T08:00:00+00:00"


def test_forecast_rows_without_publish_time_are_malformed():
    parsed = parse_forecast_rows([{"startTime": "2026-01-10T12:00:00Z", "generation": 1}])
    assert parsed.records == []
    assert parsed.malformed == 1
