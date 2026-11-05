"""Soil inputs: sand/silt/clay, pH and organic carbon per grid cell.

Providers:
  * RasterSoilProvider  - reads SoilGrids GeoTIFFs you downloaded and aggregated to 0-30 cm (needs rasterio).
  * CsvSoilProvider     - reads a pre-extracted table (cell_id, sand_pct, silt_pct, clay_pct, ph, oc_g_kg).
  * SyntheticSoilProvider - fixed demo values for offline development.
SoilGrids stores sand/silt/clay in g/kg, pH x10 and organic carbon in dg/kg; conversions below.
The ISRIC REST API was reported paused, so use downloaded GeoTIFFs (reprojected to EPSG:4326).
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from ..grid.cells import Cell


@dataclass(frozen=True)
class SoilPoint:
    sand_pct: float
    silt_pct: float
    clay_pct: float
    ph: Optional[float] = None
    oc_g_kg: Optional[float] = None

    @property
    def texture(self) -> str:
        return texture_class(self.sand_pct, self.silt_pct, self.clay_pct)


class SoilProvider(Protocol):
    def sample(self, cell: Cell) -> Optional[SoilPoint]: ...


def texture_class(sand: float, silt: float, clay: float) -> str:
    """USDA texture class from percentages (normalised to sum 100)."""
    total = sand + silt + clay
    if total <= 0:
        raise ValueError("sand + silt + clay must be positive")
    sand, silt, clay = (100.0 * x / total for x in (sand, silt, clay))
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 1.5 * clay >= 15 and silt + 2 * clay < 30:
        return "loamy_sand"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "sandy_loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt_loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy_clay_loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay_loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty_clay_loam"
    if clay >= 35 and sand > 45:
        return "sandy_clay"
    if clay >= 40 and silt >= 40:
        return "silty_clay"
    if clay >= 40 and sand <= 45 and silt < 40:
        return "clay"
    raise ValueError(f"no texture class for sand={sand:.1f} silt={silt:.1f} clay={clay:.1f}")


# ---------------------------------------------------------------------------
class CsvSoilProvider:
    def __init__(self, path: Path | str):
        self._rows: dict[str, SoilPoint] = {}
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self._rows[r["cell_id"]] = SoilPoint(
                    float(r["sand_pct"]), float(r["silt_pct"]), float(r["clay_pct"]),
                    float(r["ph"]) if r.get("ph") else None,
                    float(r["oc_g_kg"]) if r.get("oc_g_kg") else None,
                )

    def sample(self, cell: Cell) -> Optional[SoilPoint]:
        return self._rows.get(cell.cell_id)


class SyntheticSoilProvider:
    """Demo values: a clay-loam region with small deterministic variation per cell. NOT real data."""

    def sample(self, cell: Cell) -> Optional[SoilPoint]:
        h = int(hashlib.sha256(cell.cell_id.encode()).hexdigest()[:6], 16)
        j = (h % 11) - 5  # -5..+5
        return SoilPoint(sand_pct=34.0 + j, silt_pct=31.0 - j / 2, clay_pct=35.0 - j / 2,
                         ph=round(7.0 + (h % 7) * 0.1, 1), oc_g_kg=round(6.0 + (h % 5) * 0.5, 1))


class RasterSoilProvider:
    """Mean of valid pixels inside each cell, from 0-30 cm GeoTIFFs in EPSG:4326.

    `paths` maps 'sand', 'silt', 'clay', 'phh2o', 'soc' to files (SoilGrids units).
    """
    SCALE = {"sand": 10.0, "silt": 10.0, "clay": 10.0, "phh2o": 10.0, "soc": 10.0}

    def __init__(self, paths: dict[str, Path | str]):
        missing = [k for k in ("sand", "silt", "clay") if k not in paths]
        if missing:
            raise ValueError(f"missing rasters: {missing}")
        self.paths = {k: str(v) for k, v in paths.items()}

    def _mean(self, key: str, cell: Cell) -> Optional[float]:
        try:
            import rasterio
            from rasterio.windows import from_bounds
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install rasterio to read GeoTIFFs") from e
        s = cell.size_deg
        west, south, east, north = cell.ix * s, cell.iy * s, (cell.ix + 1) * s, (cell.iy + 1) * s
        with rasterio.open(self.paths[key]) as ds:
            if ds.crs is None or ds.crs.to_epsg() != 4326:
                raise ValueError(f"{self.paths[key]} must be in EPSG:4326 (reproject with gdalwarp)")
            win = from_bounds(west, south, east, north, ds.transform)
            data = ds.read(1, window=win, masked=True, boundless=True)
        valid = data.compressed()
        return float(valid.mean()) / self.SCALE[key] if valid.size else None

    def sample(self, cell: Cell) -> Optional[SoilPoint]:
        sand, silt, clay = (self._mean(k, cell) for k in ("sand", "silt", "clay"))
        if None in (sand, silt, clay):
            return None
        ph = self._mean("phh2o", cell) if "phh2o" in self.paths else None
        oc = self._mean("soc", cell) if "soc" in self.paths else None
        return SoilPoint(sand, silt, clay, ph, oc)
