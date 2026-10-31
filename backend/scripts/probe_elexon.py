"""Check the live Elexon API from YOUR machine and print what the app will see.

    cd backend && python scripts/probe_elexon.py

Run this once before the demo. It confirms that the endpoint paths, query parameters and field
names used in app/services/elexon_client.py match the live API, and shows how many WINDFOR
forecasts exist per target timestamp (the reason the decision-time rule is needed) and on which
minutes of the hour the WINDFOR targets fall (live data: :00 only, i.e. hourly).
"""

import asyncio
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.elexon_client import ElexonClient  # noqa: E402
from app.services.parsing import parse_actual_rows, parse_forecast_rows  # noqa: E402
from app.utils.time import UTC  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402


async def main() -> None:
    settings = get_settings()
    client = ElexonClient(settings)
    try:
        day = settings.delivery_window_start
        print(f"--- FUELHH (actual wind), settlement date {day} ---")
        actual_rows = await client.fetch_actual_wind_rows(day, day)
        print("rows returned:", len(actual_rows))
        print("sample row   :", actual_rows[0] if actual_rows else None)
        parsed = parse_actual_rows(actual_rows)
        print("parsed WIND  :", len(parsed.records), "| malformed:", parsed.malformed)

        print(f"\n--- WINDFOR (forecast), published in the 3 days before {day} ---")
        end = datetime(day.year, day.month, day.day, tzinfo=UTC)
        forecast_rows = await client.fetch_wind_forecast_rows(end - timedelta(days=3), end)
        print("rows returned:", len(forecast_rows))
        print("sample row   :", forecast_rows[0] if forecast_rows else None)
        parsed_f = parse_forecast_rows(forecast_rows)
        print("parsed       :", len(parsed_f.records), "| malformed:", parsed_f.malformed)
        per_target = Counter(r.start_time for r in parsed_f.records)
        if per_target:
            counts = sorted(per_target.values())
            print("forecasts per target timestamp: min", counts[0], "max", counts[-1])
            print("WINDFOR target minute-of-hour:", dict(sorted(Counter(t.minute for t in per_target).items())))
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
