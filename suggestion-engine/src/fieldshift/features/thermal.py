"""Thermal and growing-degree-day features."""

from __future__ import annotations

import math
from typing import Any


class ThermalFeatureError(ValueError):
    """Thermal calculation error."""


def _temperature(value: float) -> float:
    value = float(value)

    if not math.isfinite(value):
        raise ThermalFeatureError(
            "Temperature must be finite."
        )

    return value


def calculate_gdd(
    tmin: float,
    tmax: float,
    base_temperature: float,
    upper_temperature: float | None = None,
) -> float:
    """
    Calculate daily Growing Degree Days.

    Uses the average-temperature method with optional
    upper-temperature clipping.
    """

    tmin = _temperature(tmin)
    tmax = _temperature(tmax)
    base = _temperature(base_temperature)

    if tmax < tmin:
        raise ThermalFeatureError(
            "Maximum temperature cannot be below minimum."
        )

    if upper_temperature is not None:
        upper = _temperature(upper_temperature)

        if upper <= base:
            raise ThermalFeatureError(
                "Upper temperature must exceed base temperature."
            )

        tmin = min(max(tmin, base), upper)
        tmax = min(max(tmax, base), upper)
    else:
        tmin = max(tmin, base)
        tmax = max(tmax, base)

    average = (tmin + tmax) / 2

    return round(max(0.0, average - base), 3)


def calculate_accumulated_gdd(
    observations: list[dict[str, Any]],
    base_temperature: float,
    upper_temperature: float | None = None,
) -> float:
    """Calculate total accumulated GDD."""

    if not observations:
        raise ThermalFeatureError(
            "No temperature observations provided."
        )

    total = 0.0

    for item in observations:
        total += calculate_gdd(
            item["tmin"],
            item["tmax"],
            base_temperature,
            upper_temperature,
        )

    return round(total, 3)


def calculate_heat_stress_days(
    observations: list[dict[str, Any]],
    threshold: float,
) -> int:
    """Count days where maximum temperature exceeds threshold."""

    threshold = _temperature(threshold)

    return sum(
        _temperature(item["tmax"]) > threshold
        for item in observations
    )


def calculate_temperature_summary(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate temperature statistics."""

    if not observations:
        raise ThermalFeatureError(
            "No temperature data provided."
        )

    minimums = [
        _temperature(item["tmin"])
        for item in observations
    ]

    maximums = [
        _temperature(item["tmax"])
        for item in observations
    ]

    if any(
        maximum < minimum
        for minimum, maximum in zip(minimums, maximums)
    ):
        raise ThermalFeatureError(
            "Maximum temperature cannot be below minimum."
        )

    averages = [
        (minimum + maximum) / 2
        for minimum, maximum in zip(minimums, maximums)
    ]

    return {
        "observation_count": len(observations),
        "minimum_temperature_c": round(min(minimums), 2),
        "maximum_temperature_c": round(max(maximums), 2),
        "mean_temperature_c": round(
            sum(averages) / len(averages), 2
        ),
        "temperature_range_mean_c": round(
            sum(
                maximum - minimum
                for minimum, maximum in zip(
                    minimums, maximums
                )
            ) / len(observations),
            2,
        ),
    }


def estimate_thermal_stage(
    accumulated_gdd: float,
    crop_stages: dict[str, float],
) -> str:
    """Estimate crop growth stage from accumulated GDD."""

    accumulated_gdd = _temperature(accumulated_gdd)

    if accumulated_gdd < 0:
        raise ThermalFeatureError(
            "Accumulated GDD cannot be negative."
        )

    if not crop_stages:
        raise ThermalFeatureError(
            "Crop stage thresholds are required."
        )

    thresholds = {}

    for stage, value in crop_stages.items():
        threshold = _temperature(value)

        if threshold < 0:
            raise ThermalFeatureError(
                "Stage thresholds cannot be negative."
            )

        thresholds[stage] = threshold

    if len(set(thresholds.values())) != len(thresholds):
        raise ThermalFeatureError(
            "Crop stage thresholds must be unique."
        )

    ordered = sorted(
        thresholds.items(),
        key=lambda item: item[1],
    )

    current_stage = "before_first_stage"

    for stage, threshold in ordered:
        if accumulated_gdd >= threshold:
            current_stage = stage
        else:
            break

    return current_stage