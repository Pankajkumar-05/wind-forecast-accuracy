"""Small time helpers. All internal timestamps are timezone-aware UTC."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

HALF_HOUR = timedelta(minutes=30)
UTC = timezone.utc


def parse_utc(value: object) -> datetime:
    """Parse an ISO-8601 string into an aware UTC datetime.

    Elexon timestamps end in ``Z``. A timestamp without any offset is assumed to be UTC.
    Raises ValueError for anything that is not a parseable string.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"not a timestamp string: {value!r}")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def to_elexon_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def range_bounds_utc(start_date: date, end_date: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[first, last_exclusive) in UTC covering local days start_date..end_date inclusive."""
    first = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(UTC)
    last_exclusive = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
    return first, last_exclusive


def expected_period_starts(
    start_date: date, end_date: date, tz: ZoneInfo, step: timedelta = HALF_HOUR
) -> list[datetime]:
    """Every period start (UTC) on a regular ``step`` grid for local days start_date..end_date inclusive.

    The default step is 30 minutes (the FUELHH grid); WINDFOR uses a 60-minute step. Built from
    UTC instants so that clock-change days (23h / 25h) are counted correctly.
    """
    first, last_exclusive = range_bounds_utc(start_date, end_date, tz)
    periods: list[datetime] = []
    current = first
    while current < last_exclusive:
        periods.append(current)
        current += step
    return periods


def date_chunks(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    """Split an inclusive date range into inclusive chunks of at most ``chunk_days`` days."""
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def datetime_chunks(start: datetime, end: datetime, chunk_days: int) -> list[tuple[datetime, datetime]]:
    """Split [start, end] into contiguous chunks of at most ``chunk_days`` days."""
    chunks: list[tuple[datetime, datetime]] = []
    cursor = start
    step = timedelta(days=chunk_days)
    while cursor < end:
        chunk_end = min(cursor + step, end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end
    return chunks or [(start, end)]
