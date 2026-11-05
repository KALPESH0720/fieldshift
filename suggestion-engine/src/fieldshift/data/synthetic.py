"""Synthetic daily weather for offline development and tests. NOT real data.

Deterministic for a given cell and year. Shaped like a Deccan-plateau climate (hot dry spring,
June-September monsoon, cool dry winter) so that features and simulation behave plausibly.
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import date

from .weather import WeatherSeries, daterange

MONSOON_PEAK_DOY = 210
MONSOON_WIDTH = 38.0


def _bell(doy: int, peak: float = MONSOON_PEAK_DOY, width: float = MONSOON_WIDTH) -> float:
    return math.exp(-((doy - peak) / width) ** 2)


def _rain_scale(lon: float) -> float:
    """Wetter towards the western ghats, drier towards the interior."""
    return 1.0 + 1.9 * (73.85 - lon) if lon < 73.85 else max(0.3, 1.0 - 0.32 * (lon - 73.85))


def _seed(cell_id: str, year: int) -> int:
    return int(hashlib.sha256(f"{cell_id}:{year}".encode()).hexdigest()[:12], 16)


class SyntheticWeather:
    source = "synthetic"

    def fetch(self, cell_id: str, lat: float, lon: float, start: date, end: date) -> WeatherSeries:
        year_factor: dict[int, float] = {}
        dates, tmax, tmin, rain, rad = [], [], [], [], []
        scale = _rain_scale(lon)
        for d in daterange(start, end):
            if d.year not in year_factor:
                year_factor[d.year] = math.exp(random.Random(_seed(cell_id, d.year)).gauss(0.0, 0.22))
            rng = random.Random(_seed(cell_id, d.year * 1000 + d.timetuple().tm_yday))
            doy = d.timetuple().tm_yday
            monsoon = _bell(doy)
            tmean = 24.6 + 4.6 * math.sin(2 * math.pi * (doy - 60) / 365.0) - 2.4 * monsoon
            dtr = 12.5 - 6.5 * monsoon
            noise = rng.gauss(0.0, 1.0)
            p_rain = 0.03 + 0.72 * monsoon
            amount = 0.0
            if rng.random() < p_rain:
                amount = rng.expovariate(1.0 / (4.0 + 11.0 * monsoon)) * scale * year_factor[d.year]
            dates.append(d)
            tmax.append(round(tmean + dtr / 2.0 + noise, 2))
            tmin.append(round(tmean - dtr / 2.0 + noise * 0.5, 2))
            rain.append(round(amount, 2))
            rad.append(round(max(3.0, 21.5 - 8.0 * monsoon - (3.0 if amount > 0 else 0.0) + rng.gauss(0, 1.0)), 2))
        return WeatherSeries(cell_id, lat, lon, self.source, True, dates, tmax, tmin, rain, rad)
