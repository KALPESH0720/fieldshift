"""Soil feature extraction and suitability analysis."""

from __future__ import annotations

import math
from typing import Any


class SoilFeatureError(ValueError):
    """Soil feature validation error."""


def _number(value: float, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise SoilFeatureError(
            f"{name} must be numeric."
        ) from exc

    if not math.isfinite(result):
        raise SoilFeatureError(f"{name} must be finite.")

    return result


def classify_soil_ph(ph: float) -> str:
    """Classify soil pH."""

    ph = _number(ph, "Soil pH")

    if not 0 <= ph <= 14:
        raise SoilFeatureError("Soil pH must be between 0 and 14.")

    if ph < 5.5:
        return "strongly_acidic"

    if ph < 6.5:
        return "slightly_acidic"

    if ph <= 7.5:
        return "neutral"

    if ph <= 8.5:
        return "alkaline"

    return "strongly_alkaline"


def classify_organic_carbon(
    organic_carbon_g_kg: float,
) -> str:
    """Classify organic carbon concentration."""

    value = _number(
        organic_carbon_g_kg,
        "Organic carbon",
    )

    if value < 0:
        raise SoilFeatureError("Organic carbon cannot be negative.")

    if value < 5:
        return "very_low"

    if value < 10:
        return "low"

    if value < 20:
        return "moderate"

    return "high"


def calculate_texture_percentages(
    sand: float,
    silt: float,
    clay: float,
) -> dict[str, float]:
    """Validate and normalize soil texture percentages."""

    values = {
        "sand": _number(sand, "Sand"),
        "silt": _number(silt, "Silt"),
        "clay": _number(clay, "Clay"),
    }

    if any(value < 0 for value in values.values()):
        raise SoilFeatureError(
            "Soil texture percentages cannot be negative."
        )

    total = sum(values.values())

    if total <= 0 or abs(total - 100) > 5:
        raise SoilFeatureError(
            "Sand, silt and clay should total approximately 100%."
        )

    return {
        name: round(value / total * 100, 2)
        for name, value in values.items()
    }


def classify_texture(
    sand: float,
    silt: float,
    clay: float,
) -> str:
    """
    Return a simplified soil texture class.

    This is an indicative classification, not a replacement
    for the USDA textural triangle.
    """

    values = calculate_texture_percentages(
        sand, silt, clay
    )

    sand = values["sand"]
    silt = values["silt"]
    clay = values["clay"]

    if clay >= 40:
        return "clay"

    if sand >= 85 and clay < 10:
        return "sand"

    if sand >= 70 and clay < 15:
        return "sandy"

    if silt >= 80 and clay < 12:
        return "silt"

    if clay >= 27 and sand >= 20:
        return "clay_loam"

    if clay >= 27 and silt >= 40:
        return "silty_clay_loam"

    if sand >= 45 and clay >= 7:
        return "sandy_loam"

    if clay >= 20:
        return "loam"

    return "loam_like"


def calculate_soil_features(
    soil: dict[str, Any],
) -> dict[str, Any]:
    """Extract soil characteristics from normalized input."""

    required = {
        "ph",
        "organic_carbon_g_kg",
        "sand",
        "silt",
        "clay",
    }

    missing = required - set(soil)

    if missing:
        raise SoilFeatureError(
            f"Missing soil fields: {sorted(missing)}"
        )

    ph = _number(soil["ph"], "Soil pH")

    organic_carbon = _number(
        soil["organic_carbon_g_kg"],
        "Organic carbon",
    )

    texture = calculate_texture_percentages(
        soil["sand"],
        soil["silt"],
        soil["clay"],
    )

    return {
        "ph": ph,
        "ph_class": classify_soil_ph(ph),
        "organic_carbon_g_kg": organic_carbon,
        "organic_carbon_class": classify_organic_carbon(
            organic_carbon
        ),
        "texture_percentages": texture,
        "texture_class": classify_texture(
            soil["sand"],
            soil["silt"],
            soil["clay"],
        ),
    }


def check_crop_ph_suitability(
    soil_ph: float,
    minimum_ph: float,
    maximum_ph: float,
) -> bool:
    """Check crop-specific soil pH requirements."""

    soil_ph = _number(soil_ph, "Soil pH")
    minimum_ph = _number(minimum_ph, "Minimum pH")
    maximum_ph = _number(maximum_ph, "Maximum pH")

    if not 0 <= minimum_ph < maximum_ph <= 14:
        raise SoilFeatureError("Invalid crop pH range.")

    return minimum_ph <= soil_ph <= maximum_ph