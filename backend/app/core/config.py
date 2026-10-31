"""Application settings, loaded from environment variables (see backend/.env.example)."""

from datetime import date, time
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PRODUCTION_FRONTEND_ORIGIN = "https://wind-forecast-accuracy.vercel.app"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Elexon
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"

    # Business rule: decision-time forecast (ASSUMPTION - see README)
    decision_cutoff_time: str = "09:00"
    decision_timezone: str = "Europe/London"
    decision_days_ahead: int = 1

    # Scope: delivery days whose decision is taken in January 2026
    delivery_window_start: date = date(2026, 1, 2)
    delivery_window_end: date = date(2026, 2, 1)

    # Resolution of the WINDFOR forecast grid, in minutes. Verified on live Elexon data (Jan 2026):
    # WINDFOR target timestamps are all on the hour (60-minute gaps) while FUELHH actuals are
    # every 30 minutes. This only defines the EXPECTED forecast grid used for coverage; which
    # pairs are evaluated is always decided by exact startTime matches in the data itself.
    forecast_resolution_minutes: int = 60

    # Fetching
    forecast_publish_lookback_days: int = 3
    request_chunk_days: int = 3
    request_timeout_seconds: float = 30.0
    request_max_retries: int = 3
    request_backoff_seconds: float = 0.5
    max_concurrent_requests: int = 4

    # Metrics
    mape_min_actual_mw: float = 50.0

    # Caching
    cache_ttl_seconds: int = 3600
    cache_dir: str = ""

    # Misc
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    log_level: str = "INFO"

    @field_validator("decision_cutoff_time")
    @classmethod
    def _validate_cutoff_time(cls, value: str) -> str:
        time.fromisoformat(value)  # raises ValueError if malformed
        return value

    @model_validator(mode="after")
    def _validate_window(self) -> "Settings":
        if self.delivery_window_start > self.delivery_window_end:
            raise ValueError("DELIVERY_WINDOW_START must not be after DELIVERY_WINDOW_END")
        if self.request_chunk_days < 1:
            raise ValueError("REQUEST_CHUNK_DAYS must be >= 1")
        if self.forecast_resolution_minutes < 30 or self.forecast_resolution_minutes % 30 != 0:
            raise ValueError("FORECAST_RESOLUTION_MINUTES must be a positive multiple of 30")
        return self

    @property
    def cutoff_time(self) -> time:
        return time.fromisoformat(self.decision_cutoff_time)

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed browser origins: the CORS_ORIGINS env var plus the production frontend, always.

        Origins are normalised (whitespace and trailing slash removed, since browsers send none) and
        de-duplicated. The production origin is appended even if the env var is missing or wrong.
        """
        configured = [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]
        origins: list[str] = []
        for origin in [*configured, PRODUCTION_FRONTEND_ORIGIN]:
            if origin != "*" and origin not in origins:  # never allow a wildcard origin
                origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
