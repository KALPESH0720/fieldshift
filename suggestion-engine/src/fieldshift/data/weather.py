"""Daily weather container shared by the data clients, feature code and simulation.

Columnar and JSON-friendly. Missing values are None (NASA POWER uses -999 as its fill value).
Units: temperatures in degrees C, rain in mm/day, radiation in MJ/m2/day.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional, Protocol


@dataclass
class WeatherSeries:
    cell_id: str
    lat: float
    lon: float
    source: str
    synthetic: bool
    dates: list[date]
    tmax: list[Optional[float]]
    tmin: list[Optional[float]]
    rain: list[Optional[float]]
    rad: list[Optional[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        n = len(self.dates)
        if not self.rad:
            self.rad = [None] * n
        for name in ("tmax", "tmin", "rain", "rad"):
            if len(getattr(self, name)) != n:
                raise ValueError(f"{name} has {len(getattr(self, name))} values but there are {n} dates")
        if any(b <= a for a, b in zip(self.dates, self.dates[1:])):
            raise ValueError("dates must be strictly increasing")

    def __len__(self) -> int:
        return len(self.dates)

    def window(self, start: date, end: date) -> range:
        """Index range of the days from start to end inclusive that exist in the series."""
        lo = bisect.bisect_left(self.dates, start)
        hi = bisect.bisect_right(self.dates, end)
        return range(lo, hi)

    def coverage(self, start: date, end: date) -> float:
        """Fraction of calendar days in [start, end] that have rain and both temperatures."""
        total = (end - start).days + 1
        if total <= 0:
            return 0.0
        ok = sum(1 for i in self.window(start, end)
                 if self.tmax[i] is not None and self.tmin[i] is not None and self.rain[i] is not None)
        return ok / total

    def tmean(self, i: int) -> Optional[float]:
        if self.tmax[i] is None or self.tmin[i] is None:
            return None
        return (self.tmax[i] + self.tmin[i]) / 2.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell_id": self.cell_id, "lat": self.lat, "lon": self.lon, "source": self.source,
            "synthetic": self.synthetic, "dates": [d.isoformat() for d in self.dates],
            "tmax": self.tmax, "tmin": self.tmin, "rain": self.rain, "rad": self.rad,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "WeatherSeries":
        return cls(
            cell_id=d["cell_id"], lat=d["lat"], lon=d["lon"], source=d["source"], synthetic=d["synthetic"],
            dates=[date.fromisoformat(x) for x in d["dates"]],
            tmax=d["tmax"], tmin=d["tmin"], rain=d["rain"], rad=d.get("rad") or [],
        )

    @classmethod
    def concat(cls, parts: list["WeatherSeries"]) -> "WeatherSeries":
        if not parts:
            raise ValueError("nothing to concatenate")
        first = parts[0]
        out = cls(first.cell_id, first.lat, first.lon, first.source, first.synthetic, [], [], [], [], [])
        seen: set[date] = set()
        for p in sorted(parts, key=lambda s: s.dates[0] if s.dates else date.max):
            for i, d in enumerate(p.dates):
                if d in seen:
                    continue
                seen.add(d)
                out.dates.append(d)
                out.tmax.append(p.tmax[i])
                out.tmin.append(p.tmin[i])
                out.rain.append(p.rain[i])
                out.rad.append(p.rad[i])
        return out


class WeatherProvider(Protocol):
    def fetch(self, cell_id: str, lat: float, lon: float, start: date, end: date) -> WeatherSeries: ...


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)
