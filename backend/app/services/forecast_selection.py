"""Select, for every forecast target period, the forecast that was known at decision time.

This is the heart of the assignment. WINDFOR contains MANY forecasts for the same target
``startTime`` (re-published again and again, up to and after the delivery time). A buyer
deciding on day D-1 can only use forecasts already published. See ``DecisionRule``.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from app.core.decision_rule import DecisionRule
from app.models.domain import ActualRecord, ForecastRecord


@dataclass
class SelectionResult:
    selected: dict[datetime, ForecastRecord] = field(default_factory=dict)
    duplicates_removed: int = 0
    published_after_cutoff_excluded: int = 0
    outside_window_ignored: int = 0
    periods_with_only_late_forecasts: int = 0


def select_decision_forecasts(
    records: list[ForecastRecord],
    rule: DecisionRule,
    window_start: date,
    window_end: date,
) -> SelectionResult:
    """For each target period (``startTime``) in the window pick the latest forecast with
    ``publishTime <= cutoff(delivery day)``.

    - exact duplicates (same startTime and publishTime) are collapsed, last one wins;
    - forecasts published after the cutoff are never used;
    - target periods that only have late forecasts get no forecast (reported, not guessed).
    """
    result = SelectionResult()

    unique: dict[tuple[datetime, datetime], ForecastRecord] = {}
    for record in records:
        key = (record.start_time, record.publish_time)
        if key in unique:
            result.duplicates_removed += 1
        unique[key] = record

    seen_periods: set[datetime] = set()
    for record in unique.values():
        delivery_date = rule.delivery_date_of(record.start_time)
        if not (window_start <= delivery_date <= window_end):
            result.outside_window_ignored += 1
            continue
        seen_periods.add(record.start_time)
        if record.publish_time > rule.cutoff_for(delivery_date):
            result.published_after_cutoff_excluded += 1
            continue
        current = result.selected.get(record.start_time)
        if current is None or record.publish_time > current.publish_time:
            result.selected[record.start_time] = record

    result.periods_with_only_late_forecasts = len(seen_periods - result.selected.keys())
    return result


def dedupe_actuals(records: list[ActualRecord]) -> tuple[dict[datetime, ActualRecord], int]:
    """One actual per startTime. If Elexon returned several, the most recently published wins."""
    by_start: dict[datetime, ActualRecord] = {}
    duplicates = 0
    for record in records:
        existing = by_start.get(record.start_time)
        if existing is not None:
            duplicates += 1
            existing_rank = existing.publish_time.timestamp() if existing.publish_time else float("-inf")
            new_rank = record.publish_time.timestamp() if record.publish_time else float("-inf")
            if new_rank < existing_rank:
                continue
        by_start[record.start_time] = record
    return by_start, duplicates
