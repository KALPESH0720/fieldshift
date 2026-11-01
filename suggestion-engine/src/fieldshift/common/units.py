"""Unit conversions. The engine works internally in acres and INR per quintal."""
from __future__ import annotations

HECTARE_PER_ACRE = 0.40468564224
GUNTHA_PER_ACRE = 40.0  # 1 acre = 40 guntha (Maharashtra)


def to_acres(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u == "acre":
        return value
    if u in ("hectare", "ha"):
        return value / HECTARE_PER_ACRE
    if u == "guntha":
        return value / GUNTHA_PER_ACRE
    raise ValueError(f"unknown area unit: {unit}")


def to_inr_per_quintal(price: float, unit: str) -> float:
    u = unit.strip().lower().replace(" ", "")
    if u in ("inr/quintal", "inr/q", "rs/quintal"):
        return price
    if u in ("inr/kg", "rs/kg"):
        return price * 100.0
    if u in ("inr/tonne", "inr/ton", "inr/t"):
        return price / 10.0
    raise ValueError(f"unknown price unit: {unit}")


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
