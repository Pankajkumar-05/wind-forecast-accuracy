"""Async client for the public Elexon Insights (BMRS) stream endpoints.

NOTE ON VERIFICATION: endpoint paths and query-parameter names below follow the Elexon
Insights API documentation referenced in the assignment. They are isolated in the
constants at the top so they are trivial to adjust. Run ``python scripts/probe_elexon.py``
to confirm the live response shape from your own machine.

Design choices:
- Date ranges are split into small chunks (stream endpoints limit the range per request).
- Chunks are fetched concurrently, bounded by a semaphore (async I/O gives a real speed-up).
- Transient failures (timeouts, 429, 5xx) are retried with exponential backoff.
- If any chunk ultimately fails we RAISE; we never return a partial month as if complete.
- Raw responses for fully historical chunks can be cached on disk (CACHE_DIR).
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import ElexonResponseError, ElexonUpstreamError
from app.utils.cache import DiskCache
from app.utils.time import UTC, date_chunks, datetime_chunks, to_elexon_datetime

logger = logging.getLogger(__name__)

ACTUALS_PATH = "/datasets/FUELHH/stream"
FORECASTS_PATH = "/datasets/WINDFOR/stream"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# Chunks that ended more than this long ago are treated as final and may be disk-cached.
HISTORICAL_AGE = timedelta(days=2)


class ElexonClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http or httpx.AsyncClient(
            base_url=settings.elexon_base_url,
            timeout=settings.request_timeout_seconds,
            headers={"Accept": "application/json"},
        )
        self._owns_http = http is None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        self._disk = DiskCache(settings.cache_dir) if settings.cache_dir else None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    # ------------------------------------------------------------------ public API

    async def fetch_actual_wind_rows(self, start: date, end: date) -> list[dict[str, Any]]:
        """FUELHH rows (WIND only) for settlement dates start..end inclusive."""
        chunks = date_chunks(start, end, self._settings.request_chunk_days)
        jobs = [
            self._fetch_chunk(
                ACTUALS_PATH,
                {
                    "settlementDateFrom": chunk_start.isoformat(),
                    "settlementDateTo": chunk_end.isoformat(),
                    "fuelType": "WIND",
                    "format": "json",
                },
                chunk_end_instant=datetime.combine(chunk_end + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
            )
            for chunk_start, chunk_end in chunks
        ]
        return self._flatten(await asyncio.gather(*jobs))

    async def fetch_wind_forecast_rows(self, publish_from: datetime, publish_to: datetime) -> list[dict[str, Any]]:
        """WINDFOR rows published between ``publish_from`` and ``publish_to``."""
        chunks = datetime_chunks(publish_from, publish_to, self._settings.request_chunk_days)
        jobs = [
            self._fetch_chunk(
                FORECASTS_PATH,
                {
                    "publishDateTimeFrom": to_elexon_datetime(chunk_start),
                    "publishDateTimeTo": to_elexon_datetime(chunk_end),
                    "format": "json",
                },
                chunk_end_instant=chunk_end,
            )
            for chunk_start, chunk_end in chunks
        ]
        return self._flatten(await asyncio.gather(*jobs))

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _flatten(chunks: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        return [row for chunk in chunks for row in chunk]

    async def _fetch_chunk(self, path: str, params: dict[str, str], chunk_end_instant: datetime) -> list[dict[str, Any]]:
        cache_key = f"{self._settings.elexon_base_url}{path}?{sorted(params.items())}"
        is_historical = datetime.now(UTC) - chunk_end_instant > HISTORICAL_AGE
        if self._disk and is_historical:
            cached = self._disk.get(cache_key)
            if cached is not None:
                return cached

        async with self._semaphore:
            payload = await self._get_json(path, params)
        rows = self._extract_rows(payload, path)
        logger.info("Fetched %d rows from %s %s", len(rows), path, params)

        if self._disk and is_historical:
            self._disk.set(cache_key, rows)
        return rows

    @staticmethod
    def _extract_rows(payload: Any, path: str) -> list[dict[str, Any]]:
        """Stream endpoints return a JSON array; tolerate the {"data": [...]} envelope too."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
        raise ElexonResponseError(f"Unexpected response shape from {path}: {type(payload).__name__}")

    async def _get_json(self, path: str, params: dict[str, str]) -> Any:
        attempts = self._settings.request_max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._http.get(path, params=params)
                if response.status_code in RETRYABLE_STATUS:
                    last_error = ElexonUpstreamError(f"HTTP {response.status_code} from {path}")
                    await self._sleep_before_retry(attempt, attempts, response.headers.get("Retry-After"))
                    continue
                if response.status_code >= 400:
                    # Client errors (bad params etc.) will not fix themselves: fail immediately.
                    raise ElexonUpstreamError(f"HTTP {response.status_code} from {path}: {response.text[:200]}")
                try:
                    return response.json()
                except ValueError as exc:
                    raise ElexonResponseError(f"Invalid JSON from {path}") from exc
            except httpx.TransportError as exc:  # timeouts, connection resets, DNS...
                last_error = ElexonUpstreamError(f"Network error calling {path}: {exc!r}")
                await self._sleep_before_retry(attempt, attempts, None)
        raise last_error or ElexonUpstreamError(f"Failed to call {path}")

    async def _sleep_before_retry(self, attempt: int, attempts: int, retry_after: str | None) -> None:
        if attempt >= attempts - 1:
            return
        delay = self._settings.request_backoff_seconds * (2**attempt)
        if retry_after and retry_after.isdigit():
            delay = max(delay, min(float(retry_after), 10.0))
        logger.warning("Retrying Elexon request in %.1fs (attempt %d/%d)", delay, attempt + 1, attempts)
        await asyncio.sleep(delay)
