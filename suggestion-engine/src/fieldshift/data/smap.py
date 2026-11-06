"""SMAP L4 root-zone soil moisture (via AppEEARS) and conversion to stored water at sowing.

Product and layer names are configuration: the SPL4SMGP version number may differ from the default
below (verify in the AppEEARS product list). L4 root-zone moisture covers 0-100 cm, so 1000 mm depth.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from ..common.stats import median
from .appeears import find_column, read_point_csv

PRODUCT = "SPL4SMGP.008"   # verify the current version in AppEEARS
LAYER = "sm_rootzone"
PROFILE_DEPTH_MM = 1000.0


def parse_rootzone(csv_text: str, layer: str = LAYER) -> dict[str, dict[date, float]]:
    """cell_id -> {date: volumetric moisture m3/m3}. Fill values and out-of-range numbers are dropped."""
    rows = read_point_csv(csv_text)
    if not rows:
        return {}
    col = find_column(rows[0], layer)
    if col is None:
        raise ValueError(f"no column containing '{layer}' in {list(rows[0])}")
    sums: dict[str, dict[date, list[float]]] = {}
    for r in rows:
        try:
            v = float(r[col])
        except (TypeError, ValueError):
            continue
        if not 0.0 <= v <= 1.0:  # fill value (e.g. -9999) or garbage
            continue
        d = date.fromisoformat(r["Date"][:10])
        sums.setdefault(r["ID"], {}).setdefault(d, []).append(v)
    return {cid: {d: sum(v) / len(v) for d, v in days.items()} for cid, days in sums.items()}


def available_water_mm(theta: float, theta_wp: float, theta_fc: float, depth_mm: float = PROFILE_DEPTH_MM) -> float:
    """Plant-available water in the profile: between wilting point and field capacity."""
    return max(0.0, min(theta, theta_fc) - theta_wp) * depth_mm


def stored_water_at_sowing(
    series: dict[date, float],
    sowing: tuple[int, int],
    years: range,
    theta_wp: float,
    theta_fc: float,
    window_days: int = 3,
) -> Optional[float]:
    """Median over years of available water (mm) around the sowing date."""
    per_year: list[float] = []
    for y in years:
        target = date(y, *sowing)
        vals = [v for d, v in series.items() if abs((d - target).days) <= window_days]
        if vals:
            per_year.append(available_water_mm(sum(vals) / len(vals), theta_wp, theta_fc))
    return median(per_year)
