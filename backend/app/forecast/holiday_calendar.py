"""Region-aware holiday calendar.

Maps a business's region to the holidays that affect its sales (Islamic holidays
for the Middle East, Western holidays for Europe/US) and returns them in the shape
Prophet expects (a DataFrame of ``holiday`` name and ``ds`` date). Custom local
events can be added on top. Adding a new market is a new entry in
REGION_COUNTRIES.
"""

from __future__ import annotations

import holidays
import pandas as pd

# Region -> country codes to pull holidays for. Extend to add markets.
REGION_COUNTRIES: dict[str, list[str]] = {
    "middle_east": ["SA", "AE", "EG", "JO"],  # incl. Ramadan, Eid al-Fitr, Eid al-Adha
    "europe": ["GB", "DE", "FR"],  # incl. Christmas, Easter
    "us": ["US"],  # incl. Thanksgiving, Christmas
}

_COLUMNS = ["holiday", "ds"]


def supported_regions() -> list[str]:
    """Regions that have a holiday mapping."""
    return list(REGION_COUNTRIES)


def holiday_calendar(
    region: str,
    years: list[int],
    *,
    custom_events: dict | None = None,
) -> pd.DataFrame:
    """Return the holidays for a region and years, in Prophet's format.

    Args:
        region: account region, e.g. "middle_east" (unknown regions yield no
            holidays, so the model simply runs without them).
        years: calendar years to include, e.g. [2025, 2026].
        custom_events: optional mapping of date -> event name to add on top
            (e.g. {date(2026, 11, 27): "White Friday"}).

    Returns:
        A DataFrame with columns ``holiday`` (name) and ``ds`` (date), sorted by
        date and de-duplicated.
    """
    records: list[dict] = []

    for country in REGION_COUNTRIES.get(region, []):
        for holiday_date, name in holidays.country_holidays(country, years=years).items():
            records.append({"holiday": name, "ds": pd.Timestamp(holiday_date)})

    if custom_events:
        for event_date, name in custom_events.items():
            records.append({"holiday": name, "ds": pd.Timestamp(event_date)})

    calendar = pd.DataFrame(records, columns=_COLUMNS)
    if not calendar.empty:
        calendar = calendar.drop_duplicates().sort_values("ds").reset_index(drop=True)
    return calendar
