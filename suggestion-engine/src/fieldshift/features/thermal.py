"""Temperature features over a range of day indexes of a WeatherSeries."""
from __future__ import annotations

from typing import Optional

from ..common.stats import mean
from ..data.weather import WeatherSeries


def season_tmean(series: WeatherSeries, idx: range) -> Optional[float]:
    return mean(series.tmean(i) for i in idx)


def heat_stress_days(series: WeatherSeries, idx: range, tmax_threshold: float = 35.0) -> int:
    return sum(1 for i in idx if series.tmax[i] is not None and series.tmax[i] >= tmax_threshold)


def frost_days(series: WeatherSeries, idx: range, tmin_threshold: float = 2.0) -> int:
    return sum(1 for i in idx if series.tmin[i] is not None and series.tmin[i] <= tmin_threshold)


def growing_degree_days(series: WeatherSeries, idx: range, base: float = 10.0, cap: float = 30.0) -> float:
    total = 0.0
    for i in idx:
        tm = series.tmean(i)
        if tm is not None:
            total += max(0.0, min(tm, cap) - base)
    return total
