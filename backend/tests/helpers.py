from datetime import datetime, timezone

from app.models.domain import ActualRecord, ForecastRecord


def utc(year, month, day, hour=0, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def forecast(start: datetime, publish: datetime, mw: float) -> ForecastRecord:
    return ForecastRecord(start_time=start, publish_time=publish, generation_mw=mw)


def actual(start: datetime, mw: float, publish: datetime | None = None) -> ActualRecord:
    return ActualRecord(start_time=start, generation_mw=mw, publish_time=publish)
