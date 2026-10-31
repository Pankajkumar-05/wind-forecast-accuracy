"""Orchestrates fetching, cleaning, selection, matching and metrics.

The whole configured window (about a month: ~1,500 half-hourly actuals, ~750 hourly forecasts) is loaded ONCE, cached in
memory, and every endpoint (and every date filter in the UI) is answered from that cache.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.core.config import Settings
from app.core.decision_rule import DecisionRule
from app.core.errors import InvalidDateRangeError, NoDataError
from app.models.domain import ActualRecord, ComparisonPoint, Coverage, ForecastRecord
from app.services.comparison import build_comparison
from app.services.elexon_client import ElexonClient
from app.services.forecast_selection import dedupe_actuals, select_decision_forecasts
from app.services.metrics import DailyMetrics, Metrics, compute_daily_metrics, compute_metrics
from app.services.parsing import parse_actual_rows, parse_forecast_rows
from app.utils.cache import AsyncTTLCache
from app.utils.time import UTC

logger = logging.getLogger(__name__)


@dataclass
class CleanedDataset:
    """Everything loaded from Elexon for the configured window, cleaned and de-duplicated."""

    forecasts: dict[datetime, ForecastRecord]
    actuals: dict[datetime, ActualRecord]
    fetched_at: datetime
    raw_forecast_rows: int
    raw_actual_rows: int
    malformed_rows_skipped: int
    duplicates_removed: int
    forecasts_published_after_cutoff_excluded: int
    periods_with_only_late_forecasts: int


@dataclass
class DataQuality:
    coverage: Coverage
    warnings: list[str]
    malformed_rows_skipped: int
    duplicates_removed: int
    forecasts_published_after_cutoff_excluded: int
    fetched_at: datetime


@dataclass
class ComparisonResult:
    start: date
    end: date
    points: list[ComparisonPoint]
    quality: DataQuality


@dataclass
class MetricsResult:
    start: date
    end: date
    overall: Metrics
    daily: list[DailyMetrics]
    quality: DataQuality


@dataclass
class LatestForecast:
    delivery_date: date
    decision_cutoff: datetime
    forecasts: list[ForecastRecord]
    actual_mean_mw: float | None
    quality_warnings: list[str] = field(default_factory=list)


class AnalysisService:
    def __init__(self, settings: Settings, client: ElexonClient) -> None:
        self._settings = settings
        self._client = client
        self.rule = DecisionRule.from_settings(settings)
        self._cache: AsyncTTLCache[CleanedDataset] = AsyncTTLCache(settings.cache_ttl_seconds)

    # ------------------------------------------------------------------ loading

    async def get_dataset(self) -> CleanedDataset:
        return await self._cache.get_or_load(self._load_dataset)

    async def _load_dataset(self) -> CleanedDataset:
        s = self._settings
        publish_from = self.rule.cutoff_for(s.delivery_window_start) - timedelta(days=s.forecast_publish_lookback_days)
        publish_to = self.rule.cutoff_for(s.delivery_window_end)
        logger.info("Loading Elexon data: delivery %s..%s", s.delivery_window_start, s.delivery_window_end)

        actual_rows, forecast_rows = await asyncio.gather(
            self._client.fetch_actual_wind_rows(s.delivery_window_start, s.delivery_window_end),
            self._client.fetch_wind_forecast_rows(publish_from, publish_to),
        )

        parsed_actuals = parse_actual_rows(actual_rows)
        parsed_forecasts = parse_forecast_rows(forecast_rows)
        actuals, actual_duplicates = dedupe_actuals(parsed_actuals.records)
        selection = select_decision_forecasts(
            parsed_forecasts.records, self.rule, s.delivery_window_start, s.delivery_window_end
        )

        return CleanedDataset(
            forecasts=selection.selected,
            actuals=actuals,
            fetched_at=datetime.now(UTC),
            raw_forecast_rows=len(forecast_rows),
            raw_actual_rows=len(actual_rows),
            malformed_rows_skipped=parsed_actuals.malformed + parsed_forecasts.malformed,
            duplicates_removed=actual_duplicates + selection.duplicates_removed,
            forecasts_published_after_cutoff_excluded=selection.published_after_cutoff_excluded,
            periods_with_only_late_forecasts=selection.periods_with_only_late_forecasts,
        )

    # ------------------------------------------------------------------ range handling

    def resolve_range(self, start: date | None, end: date | None) -> tuple[date, date]:
        window_start = self._settings.delivery_window_start
        window_end = self._settings.delivery_window_end
        start = start or window_start
        end = end or window_end
        if start > end:
            raise InvalidDateRangeError("start must not be after end")
        if start < window_start or end > window_end:
            raise InvalidDateRangeError(
                f"Date range must be within {window_start} and {window_end} "
                "(delivery days whose purchase decision is taken in January 2026)"
            )
        return start, end

    # ------------------------------------------------------------------ queries

    async def comparison(self, start: date | None, end: date | None) -> ComparisonResult:
        start, end = self.resolve_range(start, end)
        dataset = await self.get_dataset()
        points, coverage = self._compare(dataset, start, end)
        return ComparisonResult(start, end, points, self._quality(dataset, coverage, start, end))

    async def metrics(self, start: date | None, end: date | None) -> MetricsResult:
        start, end = self.resolve_range(start, end)
        dataset = await self.get_dataset()
        points, coverage = self._compare(dataset, start, end)
        return MetricsResult(
            start,
            end,
            compute_metrics(points),
            compute_daily_metrics(points),
            self._quality(dataset, coverage, start, end),
        )

    async def decision_forecasts(self, start: date | None, end: date | None) -> tuple[date, date, list[ForecastRecord]]:
        start, end = self.resolve_range(start, end)
        dataset = await self.get_dataset()
        records = sorted(
            (f for f in dataset.forecasts.values() if start <= self.rule.delivery_date_of(f.start_time) <= end),
            key=lambda f: f.start_time,
        )
        return start, end, records

    async def actuals(self, start: date | None, end: date | None) -> tuple[date, date, list[ActualRecord]]:
        start, end = self.resolve_range(start, end)
        dataset = await self.get_dataset()
        records = sorted(
            (a for a in dataset.actuals.values() if start <= self.rule.delivery_date_of(a.start_time) <= end),
            key=lambda a: a.start_time,
        )
        return start, end, records

    async def latest_forecast(self, delivery_date: date | None) -> LatestForecast:
        """The decision-time forecast for one delivery day (default: latest day that has one)."""
        dataset = await self.get_dataset()
        by_day: dict[date, list[ForecastRecord]] = {}
        for forecast in dataset.forecasts.values():
            by_day.setdefault(self.rule.delivery_date_of(forecast.start_time), []).append(forecast)
        if not by_day:
            raise NoDataError("No decision-time forecasts are available for the configured period")

        if delivery_date is None:
            delivery_date = max(by_day)
        elif delivery_date not in by_day:
            raise NoDataError(f"No decision-time forecast available for delivery day {delivery_date}")

        forecasts = sorted(by_day[delivery_date], key=lambda f: f.start_time)
        day_actuals = [dataset.actuals[f.start_time].generation_mw for f in forecasts if f.start_time in dataset.actuals]
        return LatestForecast(
            delivery_date=delivery_date,
            decision_cutoff=self.rule.cutoff_for(delivery_date),
            forecasts=forecasts,
            actual_mean_mw=(sum(day_actuals) / len(day_actuals)) if day_actuals else None,
        )

    # ------------------------------------------------------------------ helpers

    def _compare(self, dataset: CleanedDataset, start: date, end: date) -> tuple[list[ComparisonPoint], Coverage]:
        return build_comparison(
            dataset.forecasts,
            dataset.actuals,
            self.rule,
            start,
            end,
            self._settings.mape_min_actual_mw,
            forecast_resolution_minutes=self._settings.forecast_resolution_minutes,
        )

    def _quality(self, dataset: CleanedDataset, coverage: Coverage, start: date, end: date) -> DataQuality:
        # NOTE: the 30-minute actual periods that fall between forecast targets are deliberately NOT a
        # warning. They have no forecast by resolution (not a data gap); the UI explains this
        # separately from `coverage.actual_periods_off_forecast_grid`.
        warnings: list[str] = []
        if coverage.expected_forecast_periods and coverage.matched_periods == 0:
            warnings.append("No forecast periods have both a decision-time forecast and an actual value in this range.")
        if coverage.missing_forecast_periods:
            warnings.append(
                f"{coverage.missing_forecast_periods} of {coverage.expected_forecast_periods} expected forecast "
                f"periods ({coverage.forecast_resolution_minutes}-minute grid) have no decision-time forecast and "
                "are excluded from the error metrics."
            )
        if coverage.missing_actual_periods:
            warnings.append(
                f"{coverage.missing_actual_periods} of {coverage.expected_forecast_periods} expected forecast "
                "periods have no actual generation value at the same start time (data may not be published yet) "
                "and are excluded from the error metrics."
            )
        if dataset.periods_with_only_late_forecasts:
            warnings.append(
                f"{dataset.periods_with_only_late_forecasts} forecast periods only had forecasts published after the "
                "decision cutoff; these were deliberately not used."
            )
        if coverage.forecast_periods_off_grid:
            warnings.append(
                f"{coverage.forecast_periods_off_grid} WINDFOR forecast timestamps are not on the expected "
                f"{coverage.forecast_resolution_minutes}-minute grid. They were still evaluated by exact start-time "
                "match, but check FORECAST_RESOLUTION_MINUTES: the data may no longer have the resolution assumed."
            )
        if dataset.malformed_rows_skipped:
            warnings.append(f"{dataset.malformed_rows_skipped} malformed Elexon rows were skipped.")
        return DataQuality(
            coverage=coverage,
            warnings=warnings,
            malformed_rows_skipped=dataset.malformed_rows_skipped,
            duplicates_removed=dataset.duplicates_removed,
            forecasts_published_after_cutoff_excluded=dataset.forecasts_published_after_cutoff_excluded,
            fetched_at=dataset.fetched_at,
        )
