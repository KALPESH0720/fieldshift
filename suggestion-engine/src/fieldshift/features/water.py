"""Rainfall and evaporative-demand features."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Optional

from ..data.weather import WeatherSeries

GSC = 0.0820  # solar constant, MJ m-2 min-1


@lru_cache(maxsize=4096)
def extraterrestrial_radiation(lat_deg: float, doy: int) -> float:
    """Ra in MJ m-2 day-1 (FAO-56 eq. 21)."""
    phi = math.radians(lat_deg)
    dr = 1.0 + 0.033 * math.cos(2 * math.pi * doy / 365.0)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365.0 - 1.39)
    x = max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta)))
    ws = math.acos(x)
    return (24 * 60 / math.pi) * GSC * dr * (ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))


def et0_hargreaves(tmax: float, tmin: float, ra: float) -> float:
    """Reference evapotranspiration, mm/day (Hargreaves-Samani); needs only temperature and latitude."""
    tmean = (tmax + tmin) / 2.0
    return max(0.0, 0.0023 * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * 0.408 * ra)


def season_rain(series: WeatherSeries, idx: range) -> float:
    return sum(series.rain[i] for i in idx if series.rain[i] is not None)


def longest_dry_spell(series: WeatherSeries, idx: range, wet_day_mm: float = 2.5) -> int:
    """Longest run of consecutive days with rain below `wet_day_mm` (2.5 mm is the usual 'rainy day' limit)."""
    best = run = 0
    for i in idx:
        r = series.rain[i]
        if r is not None and r < wet_day_mm:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def season_et0(series: WeatherSeries, idx: range) -> Optional[float]:
    total, n = 0.0, 0
    for i in idx:
        if series.tmax[i] is not None and series.tmin[i] is not None:
            total += et0_hargreaves(series.tmax[i], series.tmin[i],
                                    extraterrestrial_radiation(series.lat, series.dates[i].timetuple().tm_yday))
            n += 1
    return total if n else None
