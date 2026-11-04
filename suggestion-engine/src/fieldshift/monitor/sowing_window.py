"""
FieldShift Sowing Window Monitoring.

Evaluates sowing suitability from rainfall, temperature,
soil moisture and crop-specific thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite
from typing import Any, Mapping, Sequence


class SowingWindowError(ValueError):
    """Raised when sowing-window inputs are invalid."""


@dataclass(frozen=True)
class SowingRequirements:
    crop: str

    minimum_temperature_c: float
    maximum_temperature_c: float

    minimum_rainfall_mm: float

    minimum_soil_moisture: float | None = None

    rainfall_days_required: int = 1

    def __post_init__(self):

        if not self.crop.strip():
            raise SowingWindowError(
                "Crop name must not be empty."
            )

        if (
            self.minimum_temperature_c
            >= self.maximum_temperature_c
        ):
            raise SowingWindowError(
                "Minimum temperature must be below maximum temperature."
            )

        if self.minimum_rainfall_mm < 0:
            raise SowingWindowError(
                "Minimum rainfall cannot be negative."
            )

        if self.rainfall_days_required < 1:
            raise SowingWindowError(
                "Rainfall days required must be at least 1."
            )

        if (
            self.minimum_soil_moisture is not None
            and not 0 <= self.minimum_soil_moisture <= 1
        ):
            raise SowingWindowError(
                "Soil moisture must be between 0 and 1."
            )


def _validate_weather(weather):
    required = [
        "temperature_c",
        "rainfall_mm",
    ]

    for key in required:
        if key not in weather:
            raise SowingWindowError(
                f"Missing weather variable: {key}"
            )

    temperature = float(weather["temperature_c"])
    rainfall = float(weather["rainfall_mm"])

    if not isfinite(temperature) or not isfinite(rainfall):
        raise SowingWindowError(
            "Weather values must be finite."
        )

    if rainfall < 0:
        raise SowingWindowError(
            "Rainfall cannot be negative."
        )

    return temperature, rainfall


def evaluate_sowing_conditions(
    weather: Mapping[str, Any],
    requirements: SowingRequirements,
) -> dict[str, Any]:
    """
    Evaluate one observation or day's weather.

    Suitability is based on temperature and rainfall thresholds.
    It does not guarantee successful germination.
    """

    temperature, rainfall = _validate_weather(weather)

    temperature_suitable = (
        requirements.minimum_temperature_c
        <= temperature
        <= requirements.maximum_temperature_c
    )

    rainfall_suitable = (
        rainfall >= requirements.minimum_rainfall_mm
    )

    soil_moisture = weather.get("soil_moisture")

    if soil_moisture is not None:
        soil_moisture = float(soil_moisture)

        if not isfinite(soil_moisture):
            raise SowingWindowError(
                "Soil moisture must be finite."
            )

        if not 0 <= soil_moisture <= 1:
            raise SowingWindowError(
                "Soil moisture must be between 0 and 1."
            )

    soil_moisture_suitable = None

    if requirements.minimum_soil_moisture is not None:

        if soil_moisture is None:
            soil_moisture_suitable = None

        else:
            soil_moisture_suitable = (
                soil_moisture
                >= requirements.minimum_soil_moisture
            )

    conditions = [
        temperature_suitable,
        rainfall_suitable,
    ]

    if soil_moisture_suitable is not None:
        conditions.append(soil_moisture_suitable)

    suitable = all(conditions)

    if suitable:
        status = "suitable"

    elif not temperature_suitable:
        status = "temperature_unfavourable"

    elif not rainfall_suitable:
        status = "insufficient_rainfall"

    else:
        status = "soil_moisture_unavailable_or_unsuitable"

    return {
        "crop": requirements.crop,
        "status": status,
        "suitable": suitable,
        "temperature_c": temperature,
        "rainfall_mm": rainfall,
        "temperature_suitable": temperature_suitable,
        "rainfall_suitable": rainfall_suitable,
        "soil_moisture_suitable": soil_moisture_suitable,
        "requirements": asdict(requirements),
    }


def evaluate_sowing_window(
    weather_forecast: Sequence[Mapping[str, Any]],
    requirements: SowingRequirements,
) -> dict[str, Any]:
    """
    Evaluate a sequence of daily weather observations.

    A window is suitable when the required number of consecutive
    days meet temperature, rainfall and moisture conditions.
    """

    if not weather_forecast:
        raise SowingWindowError(
            "Weather forecast must not be empty."
        )

    daily_results = []

    for day in weather_forecast:

        result = evaluate_sowing_conditions(
            day,
            requirements,
        )

        daily_results.append(result)

    required_days = requirements.rainfall_days_required

    longest_streak = 0
    current_streak = 0

    suitable_start = None
    suitable_end = None

    for index, result in enumerate(daily_results):

        if result["suitable"]:

            current_streak += 1

            longest_streak = max(
                longest_streak,
                current_streak
            )

            if current_streak >= required_days:

                start_index = index - required_days + 1

                suitable_start = start_index
                suitable_end = index

        else:

            current_streak = 0

    suitable_window_found = (
        longest_streak >= required_days
    )

    return {
        "crop": requirements.crop,
        "window_status": (
            "suitable_window_found"
            if suitable_window_found
            else "no_suitable_window_found"
        ),
        "suitable_window_found": suitable_window_found,
        "required_consecutive_days": required_days,
        "longest_suitable_streak": longest_streak,
        "suitable_start_index": suitable_start,
        "suitable_end_index": suitable_end,
        "daily_results": daily_results,
        "interpretation": (
            "A suitable sequence of days was identified."
            if suitable_window_found
            else "No sequence met all configured requirements."
        ),
    }


def monitor_sowing_window(
    forecast,
    crop_requirements,
):
    """
    Convenience interface accepting a dictionary of crop requirements.

    Example:
        crop_requirements = {
            "crop": "rice",
            "minimum_temperature_c": 20,
            "maximum_temperature_c": 35,
            "minimum_rainfall_mm": 20,
            "rainfall_days_required": 3
        }
    """

    requirements = (
        crop_requirements
        if isinstance(
            crop_requirements,
            SowingRequirements
        )
        else SowingRequirements(**crop_requirements)
    )

    return evaluate_sowing_window(
        forecast,
        requirements,
    )