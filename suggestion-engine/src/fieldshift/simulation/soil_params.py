"""Soil hydraulic properties from texture and organic matter (Saxton & Rawls 2006 pedotransfer).

Estimated, not measured: the plan lists soil conversion as a known source of error. Values are
volumetric (m3/m3). Wilting point = 1500 kPa, field capacity = 33 kPa.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

OC_TO_OM = 1.724
DEFAULT_OM_PCT = 2.0

# Typical (sand %, clay %) per USDA class, used when only a texture class is known.
TEXTURE_CENTROIDS = {
    "sand": (92, 3), "loamy_sand": (82, 6), "sandy_loam": (65, 10), "loam": (40, 18),
    "silt_loam": (20, 15), "silt": (8, 6), "sandy_clay_loam": (60, 27), "clay_loam": (33, 33),
    "silty_clay_loam": (10, 34), "sandy_clay": (50, 42), "silty_clay": (7, 47), "clay": (20, 55),
}


@dataclass(frozen=True)
class Hydraulic:
    theta_wp: float
    theta_fc: float
    theta_sat: float
    ksat_mm_h: float

    @property
    def available_fraction(self) -> float:
        return self.theta_fc - self.theta_wp


def om_from_oc(oc_g_kg: Optional[float]) -> float:
    return DEFAULT_OM_PCT if oc_g_kg is None else max(0.1, oc_g_kg / 10.0 * OC_TO_OM)


def hydraulic_properties(sand_pct: float, clay_pct: float, om_pct: float = DEFAULT_OM_PCT) -> Hydraulic:
    if not (0 <= sand_pct <= 100 and 0 <= clay_pct <= 100 and sand_pct + clay_pct <= 100.0001):
        raise ValueError("sand and clay must be percentages that sum to at most 100")
    s, c, om = sand_pct / 100.0, clay_pct / 100.0, om_pct
    t1500t = -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om - 0.013 * c * om + 0.068 * s * c + 0.031
    t1500 = t1500t + (0.14 * t1500t - 0.02)
    t33t = -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om - 0.027 * c * om + 0.452 * s * c + 0.299
    t33 = t33t + (1.283 * t33t ** 2 - 0.374 * t33t - 0.015)
    ts33t = 0.278 * s + 0.034 * c + 0.022 * om - 0.018 * s * om - 0.027 * c * om - 0.584 * s * c + 0.078
    ts33 = ts33t + (0.636 * ts33t - 0.107)
    ts = t33 + ts33 - 0.097 * s + 0.043

    wp = min(max(t1500, 0.01), 0.45)
    fc = min(max(t33, wp + 0.02), 0.6)          # guard: field capacity must exceed wilting point
    sat = min(max(ts, fc + 0.01), 0.7)
    lam = (math.log(fc) - math.log(wp)) / (math.log(1500.0) - math.log(33.0))
    ksat = 1930.0 * max(sat - fc, 1e-4) ** (3.0 - lam)
    return Hydraulic(round(wp, 4), round(fc, 4), round(sat, 4), round(ksat, 3))


def hydraulic_from_texture(texture: str, om_pct: float = DEFAULT_OM_PCT) -> Hydraulic:
    if texture not in TEXTURE_CENTROIDS:
        raise ValueError(f"unknown texture class '{texture}'")
    sand, clay = TEXTURE_CENTROIDS[texture]
    return hydraulic_properties(sand, clay, om_pct)
