"""Pipeline P2 (deep tier): simulate the shortlisted crop sequences of one job and publish indicators.

Input is the Job the engine created on a cache miss (it carries cell, start season, irrigation,
scenario and the sequences). Output is one Indicator per simulated sequence, stored under the job's
cache key. Sequences with unknown crops or too few complete weather years are skipped and reported.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..common.http import HttpClient
from ..common.logging import get_logger
from ..common.region import RegionConfig
from ..common.seasons import parse_season
from ..data.weather_store import WeatherStore
from ..store.base import Store
from ..store.models import CellFeatures, Indicator, Job
from .crop_params import CropSim
from .indicators import build_indicator, yearly_scores
from .soil_params import (TEXTURE_CENTROIDS, Hydraulic, hydraulic_from_texture, hydraulic_properties,
                          om_from_oc)
from .water_balance import perturb, simulate_sequence

log = get_logger("fieldshift.p2")
FALLBACK_TEXTURE = "clay_loam"


class P2Error(RuntimeError):
    pass


@dataclass
class P2Config:
    region: RegionConfig
    cycle: tuple[str, ...] = ("kharif", "rabi")
    min_years: int = 8
    limited_mm: float = 100.0


def hydraulics_for_cell(cell: CellFeatures, soil_class: Optional[str] = None) -> tuple[Hydraulic, bool]:
    """(hydraulic properties, used_fallback). Prefers measured sand/clay, then a texture class."""
    if cell.sand_pct is not None and cell.clay_pct is not None:
        return hydraulic_properties(cell.sand_pct, cell.clay_pct, om_from_oc(cell.soil_organic_carbon)), False
    for texture in (soil_class, cell.soil_class):
        if texture in TEXTURE_CENTROIDS:
            return hydraulic_from_texture(texture, om_from_oc(cell.soil_organic_carbon)), False
    return hydraulic_from_texture(FALLBACK_TEXTURE), True


def initial_fraction(cell: CellFeatures, season: str, hyd: Hydraulic) -> float:
    """Profile water fraction at first sowing, from stored water at sowing (SMAP) when known, else half full."""
    climate = cell.seasons.get(season)
    capacity = 1000.0 * (hyd.theta_fc - hyd.theta_wp)
    if climate and climate.stored_water_mm_at_sowing is not None and capacity > 0:
        return min(1.0, max(0.0, climate.stored_water_mm_at_sowing / capacity))
    return 0.5


def process_job(job: Job, store: Store, weather_store: WeatherStore, crop_sim: dict[str, CropSim],
                cfg: P2Config) -> tuple[list[Indicator], list[str]]:
    for f in ("start_season", "irrigation", "scenario"):
        if getattr(job, f) is None:
            raise P2Error(f"job {job.job_id} has no {f}; the engine must set it")
    cell = store.get_cell_features(job.cell_id)
    if cell is None:
        raise P2Error(f"no feature layer for cell {job.cell_id}")
    weather = weather_store.load(job.cell_id)
    hyd, fallback = hydraulics_for_cell(cell, job.soil_class)
    warnings = [f"no soil data for {job.cell_id}: used {FALLBACK_TEXTURE}"] if fallback else []

    name, _ = parse_season(job.start_season)
    frac0 = initial_fraction(cell, name, hyd)
    delta = cell.future.get(job.scenario)
    future_weather = perturb(weather, delta.temp_delta_c or 0.0, delta.rain_change_pct or 0.0) if delta else None
    first, last = cfg.region.climate_years

    indicators: list[Indicator] = []
    for seq in job.sequences:
        ids = seq.split(">")
        unknown = [c for c in ids if c not in crop_sim]
        if unknown:
            warnings.append(f"{seq}: no simulation parameters for {unknown}")
            continue
        crops = [crop_sim[c] for c in ids]

        def run(w) -> dict[int, float]:
            by_year = {}
            for y in range(first, last + 1):
                res = simulate_sequence(w, crops, f"{name}-{y}", cfg.cycle, hyd, frac0, job.irrigation, cfg.limited_mm)
                if res:
                    by_year[y] = res
            return yearly_scores(by_year)

        baseline = run(weather)
        future = run(future_weather) if future_weather is not None else None
        ind = build_indicator(seq, baseline, future, cfg.min_years)
        if ind is None:
            warnings.append(f"{seq}: only {len(baseline)} complete years (need {cfg.min_years})")
        else:
            indicators.append(ind)
    return indicators, warnings


def run_job(job_id: str, store: Store, weather_store: WeatherStore, crop_sim: dict[str, CropSim],
            cfg: P2Config) -> Optional[Job]:
    """Process one job and write the outcome to the store (status running -> done or failed)."""
    job = store.get_job(job_id)
    if job is None:
        return None
    store.update_job(job_id, status="running")
    try:
        indicators, warnings = process_job(job, store, weather_store, crop_sim, cfg)
        for w in warnings:
            log.warning("job %s: %s", job_id, w)
        if not indicators:
            raise P2Error("no sequence could be simulated: " + "; ".join(warnings[:3]))
        store.put_indicators(job.cache_key, indicators)
        return store.update_job(job_id, status="done")
    except Exception as e:
        log.error("job %s failed: %s", job_id, e)
        return store.update_job(job_id, status="failed", error=f"{type(e).__name__}: {e}")


def publish_via_api(engine_url: str, api_key: Optional[str], job: Job, indicators: list[Indicator],
                    error: Optional[str] = None, http: Optional[HttpClient] = None) -> None:
    """Used by the Vertex component: send results to the engine, which owns the store."""
    http = http or HttpClient()
    headers = {"X-API-Key": api_key} if api_key else {}
    http.post_json(f"{engine_url.rstrip('/')}/v1/indicators", headers=headers, json={
        "job_id": job.job_id, "cache_key": job.cache_key, "error": error,
        "indicators": [i.model_dump(mode="json") for i in indicators],
    })
