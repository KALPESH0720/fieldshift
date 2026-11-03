"""Compare the crop table with FAO EcoCrop limits you exported to a simple CSV.

Expected columns: name, tmin_abs, tmin_opt, tmax_opt, tmax_abs, rain_min_abs, rain_min_opt,
rain_max_opt, rain_max_abs, ph_min_abs, ph_min_opt, ph_max_opt, ph_max_abs (one row per crop).
EcoCrop describes whole growing cycles, so differences are flagged for an agronomist to judge,
not corrected automatically. The GAEZ export format is not checked here.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

LIMIT_COLUMNS = {
    "temp_c": ("tmin_abs", "tmin_opt", "tmax_opt", "tmax_abs"),
    "rain_mm": ("rain_min_abs", "rain_min_opt", "rain_max_opt", "rain_max_abs"),
    "ph": ("ph_min_abs", "ph_min_opt", "ph_max_opt", "ph_max_abs"),
}
TOLERANCE = {"temp_c": 5.0, "rain_mm": 300.0, "ph": 1.0}


@dataclass(frozen=True)
class Discrepancy:
    crop: str
    quantity: str
    crop_table: list[float]
    ecocrop: list[float]
    max_difference: float


def load_ecocrop_csv(path: Path | str) -> dict[str, dict[str, list[float]]]:
    out: dict[str, dict[str, list[float]]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["name"].strip().lower()] = {
                q: [float(row[c]) for c in cols] for q, cols in LIMIT_COLUMNS.items()
            }
    return out


def compare_with_crop_table(ecocrop: dict[str, dict[str, list[float]]], crops: dict) -> list[Discrepancy]:
    """`crops` maps crop id -> Crop (engine.rules.Crop). Matching is by lower-case id or name."""
    found: list[Discrepancy] = []
    for cid, crop in crops.items():
        row = ecocrop.get(cid.lower()) or ecocrop.get(crop.name.lower())
        if row is None:
            continue
        for q, tol in TOLERANCE.items():
            ours, theirs = list(getattr(crop, q)), row[q]
            diff = max(abs(a - b) for a, b in zip(ours, theirs))
            if diff > tol:
                found.append(Discrepancy(cid, q, ours, theirs, round(diff, 2)))
    return found
