"""Season handling for feature extraction: which years have a usable record for a season."""
from __future__ import annotations

from ..common.region import RegionConfig
from ..data.weather import WeatherSeries

MIN_COVERAGE = 0.9


def season_years(series: WeatherSeries, region: RegionConfig, season: str, min_coverage: float = MIN_COVERAGE) -> list[int]:
    """Years (season labels) whose full season lies in the record with enough valid days."""
    win = region.seasons[season]
    first, last = region.climate_years
    out = []
    for y in range(first, last + 1):
        start, end = win.dates(y)
        if series.coverage(start, end) >= min_coverage:
            out.append(y)
    return out


def season_slice(series: WeatherSeries, region: RegionConfig, season: str, year: int) -> range:
    start, end = region.seasons[season].dates(year)
    return series.window(start, end)
