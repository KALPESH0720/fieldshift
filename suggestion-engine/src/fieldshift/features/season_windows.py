"""Agricultural season and sowing-window management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


class SeasonError(ValueError):
    """Agricultural season validation error."""


@dataclass(frozen=True)
class SeasonWindow:
    name: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int

    def __post_init__(self):
        if not self.name.strip():
            raise SeasonError("Season name cannot be empty.")

        try:
            date(2000, self.start_month, self.start_day)
            date(2000, self.end_month, self.end_day)
        except ValueError as exc:
            raise SeasonError("Invalid season dates.") from exc

    def contains(self, day: date) -> bool:
        """Check whether a date belongs to this season."""

        start = (self.start_month, self.start_day)
        end = (self.end_month, self.end_day)
        current = (day.month, day.day)

        if start <= end:
            return start <= current <= end

        # Supports seasons crossing December.
        return current >= start or current <= end


# These are configurable example calendars, not universal
# agricultural calendars for every Indian region.

DEFAULT_SEASONS = {
    "kharif": SeasonWindow(
        "Kharif", 6, 1, 10, 31
    ),
    "rabi": SeasonWindow(
        "Rabi", 11, 1, 3, 31
    ),
    "summer": SeasonWindow(
        "Summer", 3, 1, 5, 31
    ),
}


def identify_season(
    day: date,
    seasons: dict[str, SeasonWindow] | None = None,
) -> str | None:
    """Identify the agricultural season for a date."""

    seasons = seasons or DEFAULT_SEASONS

    matches = [
        name
        for name, window in seasons.items()
        if window.contains(day)
    ]

    if len(matches) > 1:
        raise SeasonError(
            "Season configuration contains overlapping windows."
        )

    return matches[0] if matches else None


def generate_sowing_window(
    start_date: date,
    duration_days: int,
) -> dict[str, date]:
    """Generate a crop sowing window."""

    if duration_days <= 0:
        raise SeasonError("Duration must be positive.")

    end_date = start_date + timedelta(days=duration_days - 1)

    return {
        "start_date": start_date,
        "end_date": end_date,
    }


def is_suitable_sowing_date(
    sowing_date: date,
    start_date: date,
    end_date: date,
) -> bool:
    """Check whether sowing is within the permitted date range."""

    if end_date < start_date:
        raise SeasonError("End date cannot precede start date.")

    return start_date <= sowing_date <= end_date


def get_sowing_status(
    current_date: date,
    start_date: date,
    end_date: date,
) -> str:
    """Classify current sowing-window status."""

    if end_date < start_date:
        raise SeasonError("Invalid sowing window.")

    if current_date < start_date:
        return "upcoming"

    if current_date <= end_date:
        return "open"

    return "closed"


def calculate_days_remaining(
    current_date: date,
    end_date: date,
) -> int:
    """Calculate remaining days in the sowing window."""

    return max(0, (end_date - current_date).days)


def get_season_information(
    day: date,
) -> dict[str, object]:
    """Return season information for a given date."""

    season = identify_season(day)

    return {
        "date": day.isoformat(),
        "season": season,
        "is_season_available": season is not None,
    }