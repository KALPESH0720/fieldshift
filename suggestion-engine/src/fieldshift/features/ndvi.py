"""NDVI vegetation health analysis for FieldShift."""

from __future__ import annotations

import math
from statistics import mean
from typing import Any


class NDVIError(ValueError):
    """NDVI processing error."""


def calculate_ndvi(nir: float, red: float) -> float | None:
    """Calculate Normalized Difference Vegetation Index."""

    nir = float(nir)
    red = float(red)

    if not math.isfinite(nir) or not math.isfinite(red):
        raise NDVIError("Reflectance values must be finite.")

    if nir < 0 or red < 0:
        raise NDVIError("Reflectance cannot be negative.")

    denominator = nir + red

    if denominator == 0:
        return None

    value = (nir - red) / denominator

    if not -1 <= value <= 1:
        return None

    return round(value, 4)


def classify_vegetation_health(ndvi: float | None) -> str:
    """Classify vegetation condition using NDVI."""

    if ndvi is None:
        return "unknown"

    if not math.isfinite(ndvi) or not -1 <= ndvi <= 1:
        raise NDVIError("Invalid NDVI value.")

    if ndvi < 0:
        return "non_vegetated"

    if ndvi < 0.2:
        return "very_low_vegetation"

    if ndvi < 0.4:
        return "sparse_vegetation"

    if ndvi < 0.6:
        return "moderate_vegetation"

    if ndvi < 0.8:
        return "healthy_vegetation"

    return "very_dense_vegetation"


def calculate_ndvi_change(
    previous_ndvi: float,
    current_ndvi: float,
) -> dict[str, Any]:
    """Calculate vegetation improvement or deterioration."""

    previous_ndvi = float(previous_ndvi)
    current_ndvi = float(current_ndvi)

    if not all(
        math.isfinite(v) and -1 <= v <= 1
        for v in (previous_ndvi, current_ndvi)
    ):
        raise NDVIError("NDVI values must be between -1 and 1.")

    change = current_ndvi - previous_ndvi

    if change > 0.05:
        trend = "improving"
    elif change < -0.05:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "previous_ndvi": previous_ndvi,
        "current_ndvi": current_ndvi,
        "change": round(change, 4),
        "trend": trend,
    }


def summarize_ndvi(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate NDVI statistics from time-series observations."""

    if not observations:
        raise NDVIError("No NDVI observations provided.")

    values = []

    for item in observations:
        value = float(item["ndvi"])

        if not math.isfinite(value) or not -1 <= value <= 1:
            raise NDVIError("Invalid NDVI observation.")

        values.append(value)

    average = mean(values)

    return {
        "observation_count": len(values),
        "mean_ndvi": round(average, 4),
        "minimum_ndvi": round(min(values), 4),
        "maximum_ndvi": round(max(values), 4),
        "latest_ndvi": round(values[-1], 4),
        "vegetation_health": classify_vegetation_health(average),
        "trend": (
            calculate_ndvi_change(values[0], values[-1])["trend"]
            if len(values) > 1
            else "insufficient_data"
        ),
    }


def calculate_ndvi_trend(
    observations: list[dict[str, Any]],
) -> float | None:
    """
    Calculate linear NDVI trend per observation.

    A positive value indicates increasing vegetation index.
    """

    if len(observations) < 2:
        return None

    values = [float(item["ndvi"]) for item in observations]

    if not all(
        math.isfinite(v) and -1 <= v <= 1 for v in values
    ):
        raise NDVIError("Invalid NDVI observations.")

    x_mean = (len(values) - 1) / 2
    y_mean = mean(values)

    numerator = sum(
        (i - x_mean) * (value - y_mean)
        for i, value in enumerate(values)
    )

    denominator = sum(
        (i - x_mean) ** 2
        for i in range(len(values))
    )

    if denominator == 0:
        return None

    return round(numerator / denominator, 6)