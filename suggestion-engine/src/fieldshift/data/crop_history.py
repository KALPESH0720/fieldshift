"""Regional crop-mix prior from district crop statistics.

Input rows: {"season": "kharif", "crop": "soybean", "area_ha": 1200.0}. Output: for each season the
share of cropped area per crop. This is a crop MIX, not a sequence model: it fills gaps when a farmer
gives no history and lowers confidence; real sequences need field-level histories or crop mapping.
"""
from __future__ import annotations

from typing import Any


def build_regional_prior(rows: list[dict[str, Any]], known_crops: set[str] | None = None) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, float]] = {}
    for r in rows:
        area = float(r["area_ha"])
        if area < 0:
            raise ValueError(f"negative area for {r}")
        if known_crops is not None and r["crop"] not in known_crops:
            continue
        season = totals.setdefault(r["season"], {})
        season[r["crop"]] = season.get(r["crop"], 0.0) + area
    prior: dict[str, dict[str, float]] = {}
    for season, crops in totals.items():
        s = sum(crops.values())
        if s > 0:
            prior[season] = {c: round(a / s, 4) for c, a in sorted(crops.items())}
    return prior
