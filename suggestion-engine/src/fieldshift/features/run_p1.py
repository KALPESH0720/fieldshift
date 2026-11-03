"""Pipeline P1: build the per-cell feature layer for a region.

Steps (each usable on its own, so the Vertex pipeline can run them as separate components):
  fetch_weather -> build_layer (features + validation + write) -> report
Output: layers/{region}/{layer_version}/cells.json in the format the engine's MemoryStore reads,
plus report.json with warnings and errors.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Optional

from ..common import io
from ..common.logging import get_logger
from ..common.paths import Layout
from ..common.region import RegionConfig, region_cells
from ..data.soilgrids import SoilProvider
from ..data.weather import WeatherProvider
from ..data.weather_store import WeatherStore
from ..grid.cells import Cell
from .future_deltas import FutureDeltaProvider
from .layer_build import CellInputs, build_cell_features, validate_cells

log = get_logger("fieldshift.p1")


@dataclass
class Providers:
    weather: WeatherProvider
    soil: SoilProvider
    future: Optional[FutureDeltaProvider] = None
    smap: Optional[dict[str, dict[date, float]]] = None   # cell_id -> series, fetched beforehand
    ndvi: Optional[dict[str, dict[date, float]]] = None
    synthetic: bool = False


class P1Error(RuntimeError):
    pass


def fetch_weather(region: RegionConfig, layout: Layout, weather: WeatherProvider, cells: list[Cell],
                  workers: int = 4, refetch: bool = False) -> dict[str, str]:
    """Download (or reuse cached) daily weather for every cell. Returns cell_id -> error message for failures."""
    store = WeatherStore(layout, region.id)
    start = date(region.climate_years[0], 1, 1)
    end = date(region.climate_years[1] + 1, 3, 31)  # rabi labelled with the last year ends the next March
    end = min(end, date(region.climate_years[1] + 1, 12, 31))

    def one(cell: Cell) -> Optional[tuple[str, str]]:
        if not refetch and store.has(cell.cell_id):
            return None
        try:
            store.save(weather.fetch(cell.cell_id, cell.center_lat, cell.center_lon, start, end))
        except Exception as e:  # record and continue; the report decides if it is fatal
            return cell.cell_id, f"{type(e).__name__}: {e}"
        return None

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        failures = [r for r in pool.map(one, cells) if r]
    return dict(failures)


def build_layer(region: RegionConfig, layout: Layout, providers: Providers, layer_version: str,
                cells: Optional[list[Cell]] = None, max_failure_fraction: float = 0.1) -> dict:
    cells = cells if cells is not None else region_cells(region)
    store = WeatherStore(layout, region.id)
    features, warnings, failed = [], [], {}
    for cell in cells:
        try:
            weather = store.load(cell.cell_id)
        except Exception as e:
            failed[cell.cell_id] = f"weather missing: {e}"
            continue
        future = {}
        if providers.future:
            for scn in region.scenarios:
                d = providers.future.delta(cell, scn)
                if d is not None:
                    future[scn] = d
        inp = CellInputs(weather=weather, soil=providers.soil.sample(cell),
                         smap=(providers.smap or {}).get(cell.cell_id),
                         ndvi=(providers.ndvi or {}).get(cell.cell_id),
                         future=future, synthetic=providers.synthetic or weather.synthetic)
        f, w = build_cell_features(cell, region, inp, layer_version)
        features.append(f)
        warnings += w

    report = validate_cells(features)
    report.update(region=region.id, layer_version=layer_version, warnings=warnings, failed_cells=failed)
    if cells and len(failed) / len(cells) > max_failure_fraction:
        report["errors"].append(f"{len(failed)} of {len(cells)} cells failed (limit {max_failure_fraction:.0%})")
    io.write_json(layout.layer_report(region.id, layer_version), report)
    if report["errors"]:
        raise P1Error(f"layer validation failed: {report['errors'][:5]}")
    io.write_json(layout.cells_file(region.id, layer_version), {"cells": [f.model_dump(mode="json") for f in features]})
    log.info("layer %s/%s written: %d cells, %d warnings", region.id, layer_version, len(features), len(warnings))
    return report


def run_p1(region: RegionConfig, layout: Layout, providers: Providers, layer_version: str,
           cells: Optional[list[Cell]] = None, workers: int = 4) -> dict:
    cells = cells if cells is not None else region_cells(region)
    failures = fetch_weather(region, layout, providers.weather, cells, workers=workers)
    if failures:
        log.warning("%d cells failed to download", len(failures))
    return build_layer(region, layout, providers, layer_version, cells)
