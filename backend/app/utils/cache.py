"""Two tiny caches. Deliberately simple - the data set is one month of half-hourly actuals and hourly forecasts."""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AsyncTTLCache(Generic[T]):
    """In-memory cache for a single async loader with a TTL.

    Concurrent callers share one in-flight load, so the Elexon API is hit once, not once
    per dashboard widget. Failed loads are not cached.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._value: T | None = None
        self._stored_at = 0.0
        self._lock = asyncio.Lock()

    def _is_fresh(self) -> bool:
        return self._value is not None and (time.monotonic() - self._stored_at) < self._ttl

    async def get_or_load(self, loader: Callable[[], Awaitable[T]]) -> T:
        if self._is_fresh():
            return self._value  # type: ignore[return-value]
        async with self._lock:
            if self._is_fresh():
                return self._value  # type: ignore[return-value]
            self._value = await loader()
            self._stored_at = time.monotonic()
            return self._value

    def clear(self) -> None:
        self._value = None


class DiskCache:
    """Optional JSON file cache for raw Elexon responses of fully historical periods."""

    def __init__(self, directory: str) -> None:
        self._dir = Path(directory)

    def _path(self, key: str) -> Path:
        return self._dir / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"

    def get(self, key: str) -> list[dict[str, Any]] | None:
        path = self._path(key)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload["rows"]
            return rows if isinstance(rows, list) else None
        except (OSError, ValueError, KeyError):
            return None

    def set(self, key: str, rows: list[dict[str, Any]]) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._path(key).write_text(json.dumps({"key": key, "rows": rows}), encoding="utf-8")
        except OSError as exc:  # caching must never break a request
            logger.warning("Could not write disk cache: %s", exc)
