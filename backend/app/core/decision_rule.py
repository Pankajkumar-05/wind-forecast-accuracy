"""The business rule that defines the "decision-time" forecast.

The assignment says day-ahead purchase decisions are made "one day before the delivery
day" but does not give an exact gate-closure time. So the cutoff is an explicit, configurable
ASSUMPTION rather than a hard-coded fact:

    cutoff(D) = (D - days_ahead) at cutoff_time, in the decision timezone

For a forecast target period starting at T (delivery day D = local date of T), the forecast used is the
one with the latest ``publishTime`` that is <= cutoff(D). Forecasts published later are
unknown to the buyer at decision time and must never be used.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import Settings


@dataclass(frozen=True)
class DecisionRule:
    cutoff_time: time
    timezone: ZoneInfo
    days_ahead: int

    @classmethod
    def from_settings(cls, settings: Settings) -> "DecisionRule":
        return cls(
            cutoff_time=settings.cutoff_time,
            timezone=ZoneInfo(settings.decision_timezone),
            days_ahead=settings.decision_days_ahead,
        )

    def delivery_date_of(self, start_time: datetime) -> date:
        """Local (decision-timezone) calendar day on which a period is delivered."""
        return start_time.astimezone(self.timezone).date()

    def cutoff_for(self, delivery_date: date) -> datetime:
        """Latest moment (UTC) at which a forecast counts as known for ``delivery_date``."""
        decision_day = delivery_date - timedelta(days=self.days_ahead)
        local_cutoff = datetime.combine(decision_day, self.cutoff_time, tzinfo=self.timezone)
        return local_cutoff.astimezone(timezone.utc)

    def describe(self) -> str:
        return (
            f"{self.days_ahead} day(s) before delivery at "
            f"{self.cutoff_time.strftime('%H:%M')} {self.timezone.key}"
        )
