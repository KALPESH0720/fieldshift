"""Region (district) configuration: the pilot area, grid size, season windows and climate years.

Loaded from knowledge/regions/<id>.yaml. P1 enumerates grid cells inside the bounding box.
"""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, field_validator, model_validator

from ..grid.cells import Cell


class SeasonWindow(BaseModel):
    start: tuple[int, int]  # (month, day)
    end: tuple[int, int]

    @field_validator("start", "end")
    @classmethod
    def _valid(cls, v: tuple[int, int]) -> tuple[int, int]:
        date(2001, v[0], v[1])  # raises ValueError for impossible month/day
        return v

    @property
    def crosses_year(self) -> bool:
        return self.end < self.start

    def dates(self, year: int) -> tuple[date, date]:
        """Start and end date of the season labelled with `year` (rabi labelled 2026 ends in 2027)."""
        start = date(year, *self.start)
        end = date(year + 1 if self.crosses_year else year, *self.end)
        return start, end


class RegionConfig(BaseModel):
    id: str
    name: str
    status: str = "draft"
    bbox: list[float]  # [min_lon, min_lat, max_lon, max_lat]
    cell_size_deg: float = 0.1
    seasons: dict[str, SeasonWindow]
    climate_years: tuple[int, int]  # inclusive; the weather record used for features and simulation
    scenarios: list[str] = ["ssp245"]
    crops: list[str] = []

    @model_validator(mode="after")
    def _check(self) -> "RegionConfig":
        min_lon, min_lat, max_lon, max_lat = self.bbox if len(self.bbox) == 4 else (0, 0, -1, -1)
        if not (min_lon < max_lon and min_lat < max_lat):
            raise ValueError("bbox must be [min_lon, min_lat, max_lon, max_lat] with min < max")
        if self.climate_years[0] > self.climate_years[1]:
            raise ValueError("climate_years must be [first, last]")
        if self.cell_size_deg <= 0:
            raise ValueError("cell_size_deg must be positive")
        return self


def load_region(path: Path | str) -> RegionConfig:
    return RegionConfig.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def region_cells(region: RegionConfig) -> list[Cell]:
    """All grid cells whose centre lies inside the bounding box, in a stable order (south to north, west to east)."""
    s = region.cell_size_deg
    min_lon, min_lat, max_lon, max_lat = region.bbox
    out = []
    for iy in range(math.floor(round(min_lat / s, 9)), math.floor(round(max_lat / s, 9)) + 1):
        for ix in range(math.floor(round(min_lon / s, 9)), math.floor(round(max_lon / s, 9)) + 1):
            c = Cell(ix=ix, iy=iy, size_deg=s)
            if min_lat <= c.center_lat <= max_lat and min_lon <= c.center_lon <= max_lon:
                out.append(c)
    return out


def find_region(directory: Path | str, region_id: str) -> Optional[RegionConfig]:
    p = Path(directory) / f"{region_id}.yaml"
    return load_region(p) if p.exists() else None
