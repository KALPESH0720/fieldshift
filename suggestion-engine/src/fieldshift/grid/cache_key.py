"""Cache key for simulation indicators.

Priority weights and prices are deliberately NOT part of the key: they only affect
scoring, so changing a slider re-ranks cached indicators without recomputation.
"""
from __future__ import annotations

import hashlib


def build_cache_key(
    cell_id: str,
    soil_class: str,
    scenario: str,
    model_version: str,
    params_version: str,
    rules_version: str,
    irrigation: str,
) -> str:
    payload = "|".join([cell_id, soil_class, scenario, model_version, params_version, rules_version, irrigation])
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def sequence_key(crops: list[str]) -> str:
    return ">".join(crops)
