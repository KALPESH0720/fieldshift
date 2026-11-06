"""Step 1: filter crops by season, climate, water and soil pH.

Suitability follows the EcoCrop idea: 0 outside the absolute limits, 1 inside the optimum,
linear in between, and the most limiting factor decides. Water supply is rain plus stored
root-zone water at sowing, so residual-moisture rabi crops are not wrongly excluded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..common.seasons import parse_season
from ..common.units import clamp
from ..store.models import CellFeatures, SeasonClimate, Soil
from .rules import Crop


def trapezoid(x: float, limits: list[float]) -> float:
    a, b, c, d = limits
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    return (x - a) / (b - a) if x < b else (d - x) / (d - c)


@dataclass
class CropFit:
    crop_id: str
    season: str
    excluded: Optional[str] = None
    excluded_params: dict = field(default_factory=dict)
    suitability: float = 0.5
    water_score: float = 0.5        # median year
    water_score_dry: float = 0.5    # dry year + future scenario
    factors: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)


def _supply(c: SeasonClimate, dry: bool, rain_change_pct: float = 0.0) -> Optional[float]:
    rain = c.rain_mm_dry_year if dry else c.rain_mm_median
    if rain is None:
        return None
    return rain * (1 + rain_change_pct / 100.0) + (c.stored_water_mm_at_sowing or 0.0)


def _adequacy(supply: Optional[float], need: float, irrigation: str) -> Optional[float]:
    if irrigation == "full":
        return 1.0
    if supply is None:
        return None
    ratio = min(1.0, supply / need)
    return min(1.0, ratio + 0.35) if irrigation == "limited" else ratio


def screen_crop(
    crop: Crop,
    season_label: str,
    cell: Optional[CellFeatures],
    soil: Soil,
    irrigation: str,
    scenario: str,
) -> CropFit:
    name = parse_season(season_label)[0]
    fit = CropFit(crop.id, season_label)
    if name not in crop.seasons:
        fit.excluded, fit.excluded_params = "SEASON_MISMATCH", {"season": name}
        return fit

    climate = cell.seasons.get(name) if cell else None
    future = cell.future.get(scenario) if cell else None
    d_temp = (future.temp_delta_c or 0.0) if future else 0.0
    d_rain = (future.rain_change_pct or 0.0) if future else 0.0
    ph = soil.ph if soil.ph is not None else (cell.soil_ph if cell else None)

    factors: dict[str, float] = {}
    dry: dict[str, float] = {}
    if climate and climate.tmean_c is not None:
        factors["temperature"] = trapezoid(climate.tmean_c, crop.temp_c)
        dry["temperature"] = trapezoid(climate.tmean_c + d_temp, crop.temp_c)
    else:
        fit.missing.append("climate:tmean")

    supply = _supply(climate, False) if climate else None
    supply_dry = _supply(climate, True, d_rain) if climate else None
    if irrigation == "rainfed":
        if supply is not None:
            factors["rainfall"] = trapezoid(supply, crop.rain_mm)
            dry["rainfall"] = trapezoid(supply_dry if supply_dry is not None else supply, crop.rain_mm)
        else:
            fit.missing.append("climate:rain")

    if ph is not None:
        factors["ph"] = dry["ph"] = trapezoid(ph, crop.ph)
    else:
        fit.missing.append("soil:ph")

    fit.factors = factors
    zero = next((k for k, v in factors.items() if v == 0.0), None)
    if zero:
        fit.excluded = f"UNSUITABLE_{'PH' if zero == 'ph' else zero.upper()}"
        fit.excluded_params = {"value": {"temperature": getattr(climate, "tmean_c", None),
                                         "rainfall": supply, "ph": ph}[zero]}
        return fit

    fit.suitability = min(factors.values()) if factors else 0.5
    suit_dry = min(dry.values()) if dry else fit.suitability

    heat = climate.heat_stress_days if climate else None
    heat_ok = 1.0 - 0.5 * clamp(heat / crop.heat_stress_days_tolerance) if heat is not None else 1.0

    adeq = _adequacy(supply, crop.water_need_mm, irrigation)
    adeq_dry = _adequacy(supply_dry, crop.water_need_mm, irrigation)
    if adeq is None and irrigation != "full":
        fit.missing.append("climate:rain")
    fit.water_score = clamp(0.5 * fit.suitability + 0.5 * (adeq if adeq is not None else 0.5) * heat_ok)
    fit.water_score_dry = clamp(0.5 * suit_dry + 0.5 * (adeq_dry if adeq_dry is not None else 0.5) * heat_ok)
    return fit
