"""Agricultural water balance and irrigation features."""

from __future__ import annotations

import math
from typing import Any


class WaterFeatureError(ValueError):
    """Water calculation error."""


def _number(value: float, name: str) -> float:
    value = float(value)

    if not math.isfinite(value):
        raise WaterFeatureError(
            f"{name} must be finite."
        )

    return value


def calculate_crop_water_requirement(
    eto_mm: float,
    crop_coefficient: float,
) -> float:
    """
    Calculate crop evapotranspiration.

    ETc = ET0 * Kc
    """

    eto = _number(eto_mm, "Reference evapotranspiration")
    kc = _number(crop_coefficient, "Crop coefficient")

    if eto < 0 or kc < 0:
        raise WaterFeatureError(
            "ET0 and crop coefficient cannot be negative."
        )

    return round(eto * kc, 3)


def calculate_effective_rainfall(
    rainfall_mm: float,
    effectiveness: float = 0.8,
) -> float:
    """Estimate effective rainfall using a configurable fraction."""

    rainfall = _number(rainfall_mm, "Rainfall")
    effectiveness = _number(
        effectiveness,
        "Rainfall effectiveness",
    )

    if rainfall < 0:
        raise WaterFeatureError("Rainfall cannot be negative.")

    if not 0 <= effectiveness <= 1:
        raise WaterFeatureError(
            "Effectiveness must be between 0 and 1."
        )

    return round(rainfall * effectiveness, 3)


def calculate_irrigation_requirement(
    crop_water_requirement_mm: float,
    effective_rainfall_mm: float,
    soil_water_contribution_mm: float = 0,
    irrigation_efficiency: float = 0.9,
) -> dict[str, float]:
    """
    Calculate net and gross irrigation requirements.

    Gross irrigation accounts for irrigation system efficiency.
    """

    etc = _number(
        crop_water_requirement_mm,
        "Crop water requirement",
    )

    rainfall = _number(
        effective_rainfall_mm,
        "Effective rainfall",
    )

    soil_water = _number(
        soil_water_contribution_mm,
        "Soil water contribution",
    )

    efficiency = _number(
        irrigation_efficiency,
        "Irrigation efficiency",
    )

    if min(etc, rainfall, soil_water) < 0:
        raise WaterFeatureError(
            "Water quantities cannot be negative."
        )

    if not 0 < efficiency <= 1:
        raise WaterFeatureError(
            "Irrigation efficiency must be greater than 0 and at most 1."
        )

    net_requirement = max(
        0.0,
        etc - rainfall - soil_water,
    )

    gross_requirement = net_requirement / efficiency

    return {
        "net_irrigation_mm": round(net_requirement, 3),
        "gross_irrigation_mm": round(gross_requirement, 3),
        "irrigation_efficiency": efficiency,
    }


def calculate_water_balance(
    initial_storage_mm: float,
    rainfall_mm: float,
    irrigation_mm: float,
    evapotranspiration_mm: float,
    drainage_mm: float = 0,
) -> dict[str, float]:
    """
    Calculate simplified soil-water balance.

    Storage = Initial storage + rainfall + irrigation
              - evapotranspiration - drainage.

    A physical upper storage limit should be supplied.
    """

    values = {
        "initial_storage": _number(
            initial_storage_mm, "Initial storage"
        ),
        "rainfall": _number(rainfall_mm, "Rainfall"),
        "irrigation": _number(irrigation_mm, "Irrigation"),
        "evapotranspiration": _number(
            evapotranspiration_mm, "Evapotranspiration"
        ),
        "drainage": _number(drainage_mm, "Drainage"),
    }

    if any(value < 0 for value in values.values()):
        raise WaterFeatureError(
            "Water balance inputs cannot be negative."
        )

    final_storage = (
        values["initial_storage"]
        + values["rainfall"]
        + values["irrigation"]
        - values["evapotranspiration"]
        - values["drainage"]
    )

    return {
        "initial_storage_mm": values["initial_storage"],
        "final_storage_mm": round(
            max(0.0, final_storage), 3
        ),
        "water_deficit_mm": round(
            max(0.0, -final_storage), 3
        ),
    }


def classify_water_stress(
    actual_et_mm: float,
    potential_et_mm: float,
) -> str:
    """
    Estimate water stress using ET ratio.

    Actual ET / Potential ET.
    """

    actual = _number(actual_et_mm, "Actual ET")
    potential = _number(
        potential_et_mm, "Potential ET"
    )

    if actual < 0 or potential < 0:
        raise WaterFeatureError(
            "Evapotranspiration cannot be negative."
        )

    if potential == 0:
        return "unknown"

    ratio = actual / potential

    if ratio >= 0.9:
        return "no_or_low_stress"

    if ratio >= 0.75:
        return "mild_stress"

    if ratio >= 0.5:
        return "moderate_stress"

    return "severe_stress"


def calculate_water_use_efficiency(
    yield_kg: float,
    water_used_m3: float,
) -> float | None:
    """Calculate crop water productivity in kg/m3."""

    yield_value = _number(yield_kg, "Crop yield")
    water = _number(water_used_m3, "Water used")

    if yield_value < 0 or water < 0:
        raise WaterFeatureError(
            "Yield and water use cannot be negative."
        )

    if water == 0:
        return None

    return round(yield_value / water, 4)


def summarize_water_conditions(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize rainfall and evapotranspiration observations."""

    if not observations:
        raise WaterFeatureError(
            "No water observations provided."
        )

    rainfall = []
    evapotranspiration = []

    for item in observations:
        rain = _number(item["rainfall_mm"], "Rainfall")
        et = _number(
            item["evapotranspiration_mm"],
            "Evapotranspiration",
        )

        if rain < 0 or et < 0:
            raise WaterFeatureError(
                "Water observations cannot be negative."
            )

        rainfall.append(rain)
        evapotranspiration.append(et)

    total_rainfall = sum(rainfall)
    total_et = sum(evapotranspiration)

    return {
        "observation_count": len(observations),
        "total_rainfall_mm": round(total_rainfall, 3),
        "total_evapotranspiration_mm": round(total_et, 3),
        "water_surplus_or_deficit_mm": round(
            total_rainfall - total_et, 3
        ),
    }