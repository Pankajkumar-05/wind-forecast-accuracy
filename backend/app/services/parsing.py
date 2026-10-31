"""Turn raw Elexon JSON rows into validated domain records.

Bad rows are skipped *and counted* so the UI can tell the user, instead of silently
producing numbers that look more complete than they are.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from app.models.domain import ActualRecord, ForecastRecord
from app.utils.time import parse_utc


@dataclass
class ParsedActuals:
    records: list[ActualRecord] = field(default_factory=list)
    malformed: int = 0
    other_fuel_types_ignored: int = 0


@dataclass
class ParsedForecasts:
    records: list[ForecastRecord] = field(default_factory=list)
    malformed: int = 0


def _parse_generation(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"invalid generation: {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite generation: {value!r}")
    return number


def parse_actual_rows(rows: list[dict[str, Any]], fuel_type: str = "WIND") -> ParsedActuals:
    """Parse FUELHH rows, keeping only ``fuel_type`` (WIND)."""
    result = ParsedActuals()
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise ValueError("row is not an object")
            row_fuel = row["fuelType"]
            if not isinstance(row_fuel, str):
                raise ValueError("fuelType is not a string")
            if row_fuel.upper() != fuel_type:
                result.other_fuel_types_ignored += 1
                continue
            publish = row.get("publishTime")
            result.records.append(
                ActualRecord(
                    start_time=parse_utc(row["startTime"]),
                    generation_mw=_parse_generation(row["generation"]),
                    publish_time=parse_utc(publish) if publish else None,
                )
            )
        except (KeyError, ValueError, TypeError):
            result.malformed += 1
    return result


def parse_forecast_rows(rows: list[dict[str, Any]]) -> ParsedForecasts:
    """Parse WINDFOR rows. Every row needs startTime, publishTime and generation."""
    result = ParsedForecasts()
    for row in rows:
        try:
            if not isinstance(row, dict):
                raise ValueError("row is not an object")
            result.records.append(
                ForecastRecord(
                    start_time=parse_utc(row["startTime"]),
                    publish_time=parse_utc(row["publishTime"]),
                    generation_mw=_parse_generation(row["generation"]),
                )
            )
        except (KeyError, ValueError, TypeError):
            result.malformed += 1
    return result
