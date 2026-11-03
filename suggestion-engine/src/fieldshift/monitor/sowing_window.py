"""Sowing-window status from observed rain.

Onset = first day on which rain accumulated over `over_days` reaches `trigger_mm` (an agro-meteorological
convention). The thresholds and the number of late-sowing days are PLACEHOLDERS to be set with the
agronomist per crop and district.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional

State = Literal["not_open", "open", "closing", "closed"]


@dataclass(frozen=True)
class SowingStatus:
    state: State
    onset: Optional[date]
    latest_sowing: date
    days_left: int


def find_onset(rain: dict[date, float], from_date: date, to_date: date, trigger_mm: float = 50.0,
               over_days: int = 3) -> Optional[date]:
    d = from_date
    while d <= to_date:
        total = sum(rain.get(d - timedelta(days=k), 0.0) for k in range(over_days))
        if total >= trigger_mm:
            return d
        d += timedelta(days=1)
    return None


def sowing_status(today: date, rain: dict[date, float], season_start: date, planned_sowing: date,
                  late_sowing_days: int = 21, warn_days: int = 10, trigger_mm: float = 50.0,
                  over_days: int = 3) -> SowingStatus:
    latest = planned_sowing + timedelta(days=late_sowing_days)
    days_left = (latest - today).days
    onset = find_onset(rain, season_start, today, trigger_mm, over_days)
    if today > latest:
        state: State = "closed"
    elif onset is None:
        state = "closing" if days_left <= warn_days else "not_open"
    else:
        state = "closing" if days_left <= warn_days else "open"
    return SowingStatus(state, onset, latest, days_left)
