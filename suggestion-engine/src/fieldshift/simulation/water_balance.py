"""Transparent daily soil-water-balance crop model (FAO-56 dual-purpose bucket).

For each day: ETc = Kc x ET0 (Hargreaves), actual ET = Ks x ETc where Ks falls below 1 once depletion
exceeds the readily available water, and the profile is recharged by effective rain and irrigation.
Seasonal relative yield (water only) follows Doorenbos-Kassam: 1 - Ky x (1 - ETa/ETc).

Simplifications (documented limits, to be replaced or calibrated):
  * water is the only yield limiter: no heat, nutrient, pest or waterlogging effects;
  * rain above 20 mm a day loses a quarter of the excess to runoff; no capillary rise;
  * between crops the profile is simulated as bare soil with very low evaporation (surface only);
  * soil hydraulic properties are estimated from texture (pedotransfer), not measured.
The simulator interface (`simulate_sequence`) is the one a WOFOST or AquaCrop adapter would implement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from ..common.seasons import next_seasons, parse_season
from ..common.units import clamp
from ..data.weather import WeatherSeries
from ..features.water import et0_hargreaves, extraterrestrial_radiation
from .crop_params import CropSim
from .soil_params import Hydraulic

RUNOFF_THRESHOLD_MM = 20.0
RUNOFF_FRACTION = 0.25
FALLOW_KC = 0.05
FALLOW_DEPTH_M = 1.0
LIMITED_EVENT_MM = 40.0
MIN_COVERAGE = 0.95


@dataclass
class SlotResult:
    crop: str
    season: str
    sowing: date
    end: date
    delay_days: int
    etc_mm: float
    eta_mm: float
    rain_mm: float
    irrigation_mm: float
    relative_yield: float
    end_fraction: float


def _et0(w: WeatherSeries, i: int) -> Optional[float]:
    if w.tmax[i] is None or w.tmin[i] is None:
        return None
    return et0_hargreaves(w.tmax[i], w.tmin[i], extraterrestrial_radiation(w.lat, w.dates[i].timetuple().tm_yday))


def _run(w: WeatherSeries, start: date, days: int, hyd: Hydraulic, fraction: float, p: float,
         kc_on, zr_on, irrigation: str, limited_mm: float):
    """Daily loop. Returns (etc, eta, rain, irrigation, end_fraction). Raises KeyError if weather is missing."""
    idx = w.window(start, start + timedelta(days=days - 1))
    if len(idx) < days * MIN_COVERAGE:
        raise KeyError("weather record does not cover the period")
    af = hyd.theta_fc - hyd.theta_wp
    taw = 1000.0 * af * zr_on(0)
    dr = taw * (1.0 - clamp(fraction))
    etc_sum = eta_sum = rain_sum = irr_sum = 0.0
    budget = limited_mm
    for n, i in enumerate(idx):
        t = (w.dates[i] - start).days
        taw = 1000.0 * af * zr_on(t)
        dr = min(dr, taw)
        raw = p * taw
        rain = w.rain[i] or 0.0
        runoff = RUNOFF_FRACTION * (rain - RUNOFF_THRESHOLD_MM) if rain > RUNOFF_THRESHOLD_MM else 0.0
        peff = rain - runoff
        et0 = _et0(w, i)
        etc = (kc_on(t) * et0) if et0 is not None else 0.0
        if dr <= raw or taw <= raw:
            ks = 1.0 if dr <= raw else 0.0
        else:
            ks = clamp((taw - dr) / (taw - raw))
        eta = ks * etc
        dr = min(max(dr - peff + eta, 0.0), taw)   # below 0 = deep percolation, above taw cannot happen physically
        # irrigation for the next day
        if irrigation != "rainfed" and dr > raw:
            if irrigation == "full":
                applied = dr
            else:
                applied = min(dr, LIMITED_EVENT_MM, budget)
                budget -= applied
            dr -= applied
            irr_sum += applied
        etc_sum += etc
        eta_sum += eta
        rain_sum += rain
    taw_end = 1000.0 * af * zr_on(days - 1)
    return etc_sum, eta_sum, rain_sum, irr_sum, clamp(1.0 - dr / taw_end) if taw_end > 0 else 0.0


def simulate_season(w: WeatherSeries, crop: CropSim, sowing: date, hyd: Hydraulic, fraction: float,
                    irrigation: str = "rainfed", limited_mm: float = 100.0) -> SlotResult:
    etc, eta, rain, irr, frac = _run(w, sowing, crop.season_days, hyd, fraction, crop.depletion_fraction,
                                     crop.kc_on, crop.root_depth_on, irrigation, limited_mm)
    ratio = eta / etc if etc > 0 else 1.0
    ry = clamp(1.0 - crop.ky * (1.0 - ratio))
    return SlotResult(crop.id, "", sowing, sowing + timedelta(days=crop.season_days - 1), 0,
                      etc, eta, rain, irr, ry, frac)


def fallow(w: WeatherSeries, start: date, end: date, hyd: Hydraulic, fraction: float) -> float:
    """Profile water fraction after bare-soil days from start to end inclusive."""
    days = (end - start).days + 1
    if days <= 0:
        return fraction
    *_, frac = _run(w, start, days, hyd, fraction, 0.5, lambda t: FALLOW_KC, lambda t: FALLOW_DEPTH_M, "rainfed", 0.0)
    return frac


def simulate_sequence(
    w: WeatherSeries, crops: list[CropSim], start_season: str, cycle: tuple[str, ...], hyd: Hydraulic,
    initial_fraction: float, irrigation: str = "rainfed", limited_mm: float = 100.0,
) -> Optional[list[SlotResult]]:
    """Simulate consecutive crops starting at `start_season` (e.g. 'kharif-2012').

    Soil water carries over between crops. A crop that has not finished before the next sowing date
    delays it (reported in `delay_days`). Returns None when the weather record is incomplete.
    """
    labels = next_seasons(start_season, len(crops), cycle)
    results: list[SlotResult] = []
    fraction = initial_fraction
    cursor: Optional[date] = None
    try:
        for crop, label in zip(crops, labels):
            name, year = parse_season(label)
            if name not in crop.sowing:
                raise ValueError(f"no sowing date for {crop.id} in season '{name}'")
            planned = date(year, *crop.sowing[name])
            sow = planned
            if cursor is not None:
                if sow > cursor:
                    fraction = fallow(w, cursor, sow - timedelta(days=1), hyd, fraction)
                else:
                    sow = cursor
            r = simulate_season(w, crop, sow, hyd, fraction, irrigation, limited_mm)
            r.season, r.delay_days = label, (sow - planned).days
            results.append(r)
            fraction, cursor = r.end_fraction, r.end + timedelta(days=1)
    except KeyError:
        return None
    return results


def perturb(w: WeatherSeries, temp_delta_c: float = 0.0, rain_change_pct: float = 0.0) -> WeatherSeries:
    """A copy of the weather with a climate-change factor applied (temperature shift, rain scaling)."""
    f = 1.0 + rain_change_pct / 100.0
    return WeatherSeries(
        w.cell_id, w.lat, w.lon, w.source + "+delta", w.synthetic, list(w.dates),
        [None if v is None else v + temp_delta_c for v in w.tmax],
        [None if v is None else v + temp_delta_c for v in w.tmin],
        [None if v is None else v * f for v in w.rain], list(w.rad),
    )


def fallow_moisture_series(w: WeatherSeries, hyd: Hydraulic, start: date, end: date,
                           initial_fraction: float = 0.2) -> dict[date, float]:
    """Volumetric root-zone moisture (m3/m3) day by day under bare soil. Stand-in for SMAP in offline
    development only: it is a model, not an observation."""
    out: dict[date, float] = {}
    frac = initial_fraction
    d = start
    while d <= end:
        try:
            frac = fallow(w, d, d, hyd, frac)
        except KeyError:
            d += timedelta(days=1)
            continue
        out[d] = hyd.theta_wp + frac * (hyd.theta_fc - hyd.theta_wp)
        d += timedelta(days=1)
    return out
