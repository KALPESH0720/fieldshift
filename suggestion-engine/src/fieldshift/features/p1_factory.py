"""Builds P1 providers from simple string options, so the CLI, tests and Vertex components share one path."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

from ..common import io
from ..common.config import REPO_ROOT
from ..common.paths import Layout
from ..common.region import RegionConfig, find_region, region_cells
from ..data.modis import parse_ndvi
from ..data.power import PowerClient
from ..data.smap import parse_rootzone
from ..data.soilgrids import CsvSoilProvider, RasterSoilProvider, SoilProvider, SyntheticSoilProvider
from ..data.synthetic import SyntheticWeather
from ..data.weather import WeatherProvider
from ..data.weather_store import WeatherStore
from ..simulation.soil_params import hydraulic_from_texture, hydraulic_properties, om_from_oc
from ..simulation.water_balance import fallow_moisture_series
from ..store.models import FutureDelta
from .future_deltas import StaticDeltaProvider
from .run_p1 import Providers, build_layer, fetch_weather

KNOWLEDGE_REGIONS = REPO_ROOT / "knowledge" / "regions"


def default_regions_dir() -> Path:
    """knowledge/regions, or the folder named by FIELDSHIFT_REGIONS_DIR (read at call time)."""
    return Path(os.environ.get("FIELDSHIFT_REGIONS_DIR") or KNOWLEDGE_REGIONS)


def load_region_by_id(region_id: str, regions_dir: Path | str | None = None) -> RegionConfig:
    directory = Path(regions_dir) if regions_dir else default_regions_dir()
    r = find_region(directory, region_id)
    if r is None:
        raise ValueError(f"no region file '{region_id}.yaml' in {directory}")
    return r


def make_weather(source: str) -> WeatherProvider:
    if source == "power":
        return PowerClient()
    if source == "synthetic":
        return SyntheticWeather()
    raise ValueError(f"unknown weather source '{source}' (use power or synthetic)")


def make_soil(source: str, path: Optional[str]) -> SoilProvider:
    if source == "synthetic":
        return SyntheticSoilProvider()
    if source == "csv":
        if not path:
            raise ValueError("soil_source 'csv' needs soil_path")
        return CsvSoilProvider(path)
    if source == "raster":
        if not path:
            raise ValueError("soil_source 'raster' needs soil_path (a JSON file mapping sand/silt/clay/phh2o/soc to GeoTIFFs)")
        return RasterSoilProvider(json.loads(io.read_text(path)))
    raise ValueError(f"unknown soil source '{source}' (use synthetic, csv or raster)")


def make_future(path: Optional[str], synthetic: bool):
    if path:
        raw = json.loads(io.read_text(path))
        return StaticDeltaProvider({k: FutureDelta(**v) for k, v in raw.items()})
    if synthetic:
        return StaticDeltaProvider({"ssp245": FutureDelta(temp_delta_c=1.2, rain_change_pct=5.0)})
    return None




def run_fetch(region_id: str, data_root: str, source: str, workers: int = 4, refetch: bool = False,
              regions_dir: Path | str | None = None) -> int:
    """P1 step 1. Returns the number of cells that failed to download."""
    region = load_region_by_id(region_id, regions_dir)
    failures = fetch_weather(region, Layout(data_root), make_weather(source), region_cells(region), workers, refetch)
    return len(failures)


def run_build(region_id: str, data_root: str, layer_version: str, source: str = "power", soil_source: str = "synthetic",
              soil_path: Optional[str] = None, smap_csv: Optional[str] = None, ndvi_csv: Optional[str] = None,
              future_json: Optional[str] = None, regions_dir: Path | str | None = None) -> dict:
    """P1 step 2: build, validate and write the layer. `source='synthetic'` also stands in for SMAP (dev only)."""
    region = load_region_by_id(region_id, regions_dir)
    layout = Layout(data_root)
    synthetic = source == "synthetic" or soil_source == "synthetic"
    soil = make_soil(soil_source, soil_path)
    smap = parse_rootzone(io.read_text(smap_csv)) if smap_csv else None
    ndvi = parse_ndvi(io.read_text(ndvi_csv)) if ndvi_csv else None
    if source == "synthetic" and smap is None:
        smap = _synthetic_smap(region, layout, soil)
    providers = Providers(weather=make_weather(source), soil=soil, future=make_future(future_json, synthetic),
                          smap=smap, ndvi=ndvi, synthetic=synthetic)
    return build_layer(region, layout, providers, layer_version)


def _synthetic_smap(region: RegionConfig, layout: Layout, soil: SoilProvider) -> dict:
    """Development stand-in for SMAP: modelled bare-soil moisture. Not an observation."""
    store = WeatherStore(layout, region.id)
    out = {}
    start, end = date(region.climate_years[0], 1, 1), date(region.climate_years[1], 12, 31)
    for cell in region_cells(region):
        if not store.has(cell.cell_id):
            continue
        p = soil.sample(cell)
        hyd = (hydraulic_properties(p.sand_pct, p.clay_pct, om_from_oc(p.oc_g_kg)) if p
               else hydraulic_from_texture("clay_loam"))
        out[cell.cell_id] = fallow_moisture_series(store.load(cell.cell_id), hyd, start, end)
    return out
