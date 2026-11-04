"""Future climate delta calculations for FieldShift."""

from __future__ import annotations

import math
from typing import Any


class ClimateDeltaError(ValueError):
    """Raised when climate comparison data is invalid."""


def _validate_number(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ClimateDeltaError(f"{name} must be numeric.")

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ClimateDeltaError(
            f"{name} must be numeric."
        ) from exc

    if not math.isfinite(result):
        raise ClimateDeltaError(f"{name} must be finite.")

    return result


def calculate_temperature_delta(
    historical: float,
    future: float,
) -> float:
    """Calculate future temperature increase in Celsius."""

    historical = _validate_number(historical, "Historical temperature")
    future = _validate_number(future, "Future temperature")

    return round(future - historical, 3)


def calculate_rainfall_delta(
    historical: float,
    future: float,
) -> dict[str, float | None]:
    """Calculate rainfall difference and percentage change."""

    historical = _validate_number(historical, "Historical rainfall")
    future = _validate_number(future, "Future rainfall")

    if historical < 0 or future < 0:
        raise ClimateDeltaError("Rainfall cannot be negative.")

    difference = future - historical

    percentage = (
        difference / historical * 100
        if historical > 0
        else None
    )

    return {
        "difference_mm": round(difference, 3),
        "change_percent": (
            round(percentage, 2)
            if percentage is not None else None
        ),
    }


def classify_climate_risk(
    temperature_delta: float,
    rainfall_change_percent: float | None,
) -> list[str]:
    """Identify potential climate risks."""

    risks = []

    if temperature_delta >= 2:
        risks.append("high_temperature_increase")
    elif temperature_delta >= 1:
        risks.append("moderate_temperature_increase")

    if rainfall_change_percent is not None:
        if rainfall_change_percent <= -30:
            risks.append("severe_rainfall_decline")
        elif rainfall_change_percent <= -15:
            risks.append("rainfall_decline")
        elif rainfall_change_percent >= 30:
            risks.append("excessive_rainfall_increase")

    return risks


def calculate_future_deltas(
    historical: dict[str, float],
    future: dict[str, float],
    scenario: str = "unspecified",
) -> dict[str, Any]:
    """
    Compare historical and projected climate conditions.

    Expected keys:
        temperature_c
        rainfall_mm
    """

    required = {"temperature_c", "rainfall_mm"}

    if not required.issubset(historical):
        raise ClimateDeltaError("Historical climate data is incomplete.")

    if not required.issubset(future):
        raise ClimateDeltaError("Future climate data is incomplete.")

    temp_delta = calculate_temperature_delta(
        historical["temperature_c"],
        future["temperature_c"],
    )

    rainfall_delta = calculate_rainfall_delta(
        historical["rainfall_mm"],
        future["rainfall_mm"],
    )

    risks = classify_climate_risk(
        temp_delta,
        rainfall_delta["change_percent"],
    )

    return {
        "scenario": scenario,
        "temperature_delta_c": temp_delta,
        "rainfall_difference_mm": rainfall_delta["difference_mm"],
        "rainfall_change_percent": rainfall_delta["change_percent"],
        "climate_risks": risks,
    }