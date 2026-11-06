"""Pipeline P1, cell level: weather + soil + SMAP + NDVI + future deltas -> CellFeatures.

Statistics are taken across years: medians for typical values, the 20th percentile of seasonal
rain for a dry year, the 80th percentile of the longest dry spell for a bad year.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..common.region import RegionConfig
from ..common.stats import mean, median, percentile
from ..data.smap import stored_water_at_sowing
from ..data.soilgrids import SoilPoint
from ..data.weather import WeatherSeries
from ..grid.cells import Cell
from ..simulation.soil_params import hydraulic_from_texture, hydraulic_properties, om_from_oc
from ..store.models import CellFeatures, FutureDelta, SeasonClimate
from .ndvi import ndvi_variability
from .season_windows import season_slice, season_years
from .soil import soil_fields
from .thermal import heat_stress_days, season_tmean
from .water import longest_dry_spell, season_rain

MIN_YEARS = 8
DROUGHT_FRACTION_OF_MEDIAN = 0.75


@dataclass
class CellInputs:
    weather: WeatherSeries
    soil: Optional[SoilPoint] = None
    smap: Optional[dict[date, float]] = None      # volumetric root-zone moisture by date
    ndvi: Optional[dict[date, float]] = None
    future: dict[str, FutureDelta] = field(default_factory=dict)
    synthetic: bool = False


def _hydraulics(soil: Optional[SoilPoint]):
    if soil is None:
        return hydraulic_from_texture("clay_loam")  # fallback; the report warns about missing soil
    return hydraulic_properties(soil.sand_pct, soil.clay_pct, om_from_oc(soil.oc_g_kg))


def build_cell_features(cell: Cell, region: RegionConfig, inp: CellInputs, layer_version: str) -> tuple[CellFeatures, list[str]]:
    warnings: list[str] = []
    seasons: dict[str, SeasonClimate] = {}
    rain_by_season_year: dict[str, dict[int, float]] = {}
    hyd = _hydraulics(inp.soil)
    if inp.soil is None:
        warnings.append(f"{cell.cell_id}: no soil data")

    for name, win in region.seasons.items():
        years = season_years(inp.weather, region, name)
        if len(years) < MIN_YEARS:
            warnings.append(f"{cell.cell_id}: only {len(years)} usable years for season '{name}' (need {MIN_YEARS})")
            continue
        rains, temps, heat, dry = [], [], [], []
        for y in years:
            idx = season_slice(inp.weather, region, name, y)
            rains.append(season_rain(inp.weather, idx))
            temps.append(season_tmean(inp.weather, idx))
            heat.append(float(heat_stress_days(inp.weather, idx)))
            dry.append(float(longest_dry_spell(inp.weather, idx)))
        rain_by_season_year[name] = dict(zip(years, rains))
        stored = None
        if inp.smap:
            stored = stored_water_at_sowing(inp.smap, win.start, range(*(region.climate_years[0], region.climate_years[1] + 1)),
                                            hyd.theta_wp, hyd.theta_fc)
            if stored is None:
                warnings.append(f"{cell.cell_id}: no SMAP values near sowing for '{name}'")
        seasons[name] = SeasonClimate(
            rain_mm_median=round(median(rains), 1),
            rain_mm_dry_year=round(percentile(rains, 20), 1),
            stored_water_mm_at_sowing=None if stored is None else round(stored, 1),
            tmean_c=round(mean(temps), 2),
            heat_stress_days=round(median(heat), 1),
            longest_dry_spell_days=round(percentile(dry, 80), 1),
        )

    # Rain-based drought proxy: share of years whose total rain over all seasons is below 75% of the median.
    drought = None
    if rain_by_season_year:
        common_years = set.intersection(*(set(d) for d in rain_by_season_year.values()))
        totals = [sum(d[y] for d in rain_by_season_year.values()) for y in sorted(common_years)]
        if len(totals) >= MIN_YEARS:
            limit = DROUGHT_FRACTION_OF_MEDIAN * median(totals)
            drought = round(sum(1 for t in totals if t < limit) / len(totals), 3)

    ndvi_cv = None
    if inp.ndvi:
        v = ndvi_variability(inp.ndvi, region, range(region.climate_years[0], region.climate_years[1] + 1))
        ndvi_cv = None if v is None else round(v, 4)

    feats = CellFeatures(
        cell_id=cell.cell_id, layer_version=layer_version, synthetic=inp.synthetic,
        seasons=seasons, drought_frequency=drought, ndvi_cv=ndvi_cv, future=dict(inp.future),
        **soil_fields(inp.soil),
    )
    return feats, warnings


def validate_cells(cells: list[CellFeatures]) -> dict:
    """Range and consistency checks. Any entry in `errors` should stop the pipeline."""
    errors: list[str] = []
    ids = [c.cell_id for c in cells]
    if len(ids) != len(set(ids)):
        errors.append("duplicate cell ids")
    for c in cells:
        tag = c.cell_id
        if c.soil_ph is not None and not 0 <= c.soil_ph <= 14:
            errors.append(f"{tag}: soil_ph {c.soil_ph} out of range")
        if c.drought_frequency is not None and not 0 <= c.drought_frequency <= 1:
            errors.append(f"{tag}: drought_frequency out of range")
        for name, s in c.seasons.items():
            if s.rain_mm_median is not None and s.rain_mm_median < 0:
                errors.append(f"{tag}/{name}: negative rain")
            if None not in (s.rain_mm_dry_year, s.rain_mm_median) and s.rain_mm_dry_year > s.rain_mm_median + 1e-6:
                errors.append(f"{tag}/{name}: dry-year rain exceeds median rain")
            if s.tmean_c is not None and not -10 <= s.tmean_c <= 45:
                errors.append(f"{tag}/{name}: tmean {s.tmean_c} out of range")
            if s.stored_water_mm_at_sowing is not None and s.stored_water_mm_at_sowing < 0:
                errors.append(f"{tag}/{name}: negative stored water")
    return {
        "n_cells": len(cells),
        "n_with_climate": sum(1 for c in cells if c.seasons),
        "n_with_soil": sum(1 for c in cells if c.soil_class),
        "errors": errors,
    }
