"""
FieldShift Agricultural Performance Indicators.

Calculates yield efficiency, harvest index, nitrogen balance,
gross margin and soil changes.
"""

from math import isfinite
from typing import Mapping, Any


class IndicatorError(ValueError):
    """Raised when indicator inputs are invalid."""


def validate_value(name, value, minimum=None):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise IndicatorError(f"{name} must be numeric.") from exc

    if not isfinite(number):
        raise IndicatorError(f"{name} must be finite.")

    if minimum is not None and number < minimum:
        raise IndicatorError(f"{name} cannot be below {minimum}.")

    return number


def water_use_efficiency(yield_kg_ha, water_use_mm):
    """
    Calculate crop yield per unit of water consumed.

    Result: kg/ha/mm.
    """

    yield_value = validate_value(
        "yield_kg_ha", yield_kg_ha, 0
    )

    water = validate_value(
        "water_use_mm", water_use_mm, 0
    )

    if water == 0:
        return None

    return round(yield_value / water, 3)


def harvest_index(grain_yield_kg_ha, biomass_kg_ha):
    """
    Harvest Index = Economic Yield / Biological Yield.
    """

    grain = validate_value(
        "grain_yield_kg_ha", grain_yield_kg_ha, 0
    )

    biomass = validate_value(
        "biomass_kg_ha", biomass_kg_ha, 0
    )

    if biomass == 0:
        return None

    if grain > biomass:
        raise IndicatorError(
            "Grain yield cannot exceed aboveground biomass."
        )

    return round(grain / biomass, 4)


def nitrogen_balance(inputs, outputs):
    """
    Partial nitrogen balance.

    Inputs and outputs should be supplied in kg N/ha.
    """

    total_input = sum(
        validate_value(f"input {key}", value, 0)
        for key, value in inputs.items()
    )

    total_output = sum(
        validate_value(f"output {key}", value, 0)
        for key, value in outputs.items()
    )

    return {
        "nitrogen_inputs_kg_ha": round(total_input, 2),
        "nitrogen_outputs_kg_ha": round(total_output, 2),
        "partial_nitrogen_balance_kg_ha": round(
            total_input - total_output, 2
        )
    }


def gross_margin(
    yield_kg_ha,
    price_per_kg,
    variable_costs_per_ha,
    subsidy_per_ha=0
):
    """
    Calculate crop gross margin.

    Gross Margin = Revenue - Variable Costs + Subsidies.
    """

    yield_value = validate_value("yield", yield_kg_ha, 0)
    price = validate_value("price", price_per_kg, 0)
    costs = validate_value("costs", variable_costs_per_ha, 0)
    subsidy = validate_value("subsidy", subsidy_per_ha, 0)

    revenue = yield_value * price

    return {
        "gross_revenue_per_ha": round(revenue, 2),
        "total_costs_per_ha": round(costs, 2),
        "subsidy_per_ha": round(subsidy, 2),
        "gross_margin_per_ha": round(
            revenue - costs + subsidy, 2
        )
    }


def soil_change_indicators(before, after):
    """
    Compare two soil observations.

    Measurements must use the same units and sampling depth.
    """

    keys = [
        "ph",
        "organic_carbon_pct",
        "nitrogen_kg_ha",
        "available_water_capacity"
    ]

    changes = {}

    for key in keys:

        if key in before and key in after:

            old = validate_value(f"before.{key}", before[key])
            new = validate_value(f"after.{key}", after[key])

            changes[f"{key}_change"] = round(new - old, 4)

    return changes


def summarize_simulation(
    yield_kg_ha=None,
    water_use_mm=None,
    biomass_kg_ha=None,
    grain_yield_kg_ha=None,
    nitrogen_inputs=None,
    nitrogen_outputs=None
):
    """Create a consolidated simulation indicator report."""

    result = {}

    if yield_kg_ha is not None and water_use_mm is not None:
        result["water_use_efficiency_kg_ha_mm"] = (
            water_use_efficiency(yield_kg_ha, water_use_mm)
        )

    if biomass_kg_ha is not None and grain_yield_kg_ha is not None:
        result["harvest_index"] = harvest_index(
            grain_yield_kg_ha,
            biomass_kg_ha
        )

    if nitrogen_inputs is not None and nitrogen_outputs is not None:
        result.update(
            nitrogen_balance(nitrogen_inputs, nitrogen_outputs)
        )

    return result