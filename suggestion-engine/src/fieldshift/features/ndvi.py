"""NDVI features: season mean per year and year-to-year variability."""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..common.region import RegionConfig
from ..common.stats import cv, mean


def season_ndvi(ndvi: dict[date, float], region: RegionConfig, season: str, years: range) -> dict[int, float]:
    win = region.seasons[season]
    out: dict[int, float] = {}
    for y in years:
        start, end = win.dates(y)
        m = mean(v for d, v in ndvi.items() if start <= d <= end)
        if m is not None:
            out[y] = m
    return out


def ndvi_variability(ndvi: dict[date, float], region: RegionConfig, years: range) -> Optional[float]:
    """Coefficient of variation of the season-mean NDVI across years, pooled over seasons."""
    per_year: list[float] = []
    for season in region.seasons:
        per_year += list(season_ndvi(ndvi, region, season, years).values())
    return cv(per_year)
