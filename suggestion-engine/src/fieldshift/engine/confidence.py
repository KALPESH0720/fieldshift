"""Confidence level and human-review flag.

Missing inputs lower confidence; they are never silently defaulted. Uncertain cases are
flagged for a human advisor instead of guessed, as the implementation plan requires.
"""
from __future__ import annotations

from dataclasses import dataclass

DEDUCTIONS = {
    "climate_layer": 1.5,   # no grid-cell features at all
    "crop_history": 0.75,
    "unknown_history_crop": 0.5,
    "soil:ph": 0.25,
    "price": 0.5,
    "cost": 0.25,
    "close_call": 0.5,
    "single_option": 0.5,
}


@dataclass
class Assessment:
    level: str
    needs_human_review: bool


def downgrade(level: str) -> str:
    return {"high": "medium", "medium": "low", "low": "low"}[level]


def assess(missing_inputs: list[str], notes: list[str], n_options: int, top_gap: float | None) -> Assessment:
    points = 3.0
    seen: set[str] = set()
    for m in missing_inputs:
        key = "price" if m.startswith("price:") else "cost" if m.startswith("cost:") else m
        if key in DEDUCTIONS and key not in seen:
            points -= DEDUCTIONS[key]
            seen.add(key)
    if any(n.startswith("UNKNOWN_HISTORY_CROP") for n in notes):
        points -= DEDUCTIONS["unknown_history_crop"]
    if top_gap is not None and top_gap < 0.02:
        points -= DEDUCTIONS["close_call"]
    if n_options == 1:
        points -= DEDUCTIONS["single_option"]
    level = "high" if points >= 2.5 else "medium" if points >= 1.5 else "low"
    if n_options == 0:
        level = "low"  # nothing to recommend: a human advisor decides
    return Assessment(level, needs_human_review=(n_options == 0 or level == "low"))
