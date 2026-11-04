"""
FieldShift Soil Parameter Module.

Validates soil properties, classifies soil texture and estimates
root-zone water availability for agricultural simulations.
"""

from dataclasses import dataclass, asdict
from typing import Any, Mapping
from math import isfinite


class SoilParameterError(ValueError):
    """Invalid soil parameter."""


def validate_number(name, value, minimum=None, maximum=None):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SoilParameterError(f"{name} must be numeric.") from exc

    if not isfinite(number):
        raise SoilParameterError(f"{name} must be finite.")

    if minimum is not None and number < minimum:
        raise SoilParameterError(f"{name} must be >= {minimum}.")

    if maximum is not None and number > maximum:
        raise SoilParameterError(f"{name} must be <= {maximum}.")

    return number


@dataclass(frozen=True)
class SoilProfile:
    ph: float
    organic_carbon_pct: float
    sand_pct: float
    silt_pct: float
    clay_pct: float
    depth_cm: float = 100.0
    bulk_density_g_cm3: float | None = None
    field_capacity: float | None = None
    wilting_point: float | None = None
    source: str = "user_or_dataset"
    confidence: str = "medium"

    def __post_init__(self):
        validate_number("pH", self.ph, 0, 14)
        validate_number("organic carbon", self.organic_carbon_pct, 0, 20)

        for name in ("sand_pct", "silt_pct", "clay_pct"):
            validate_number(name, getattr(self, name), 0, 100)

        total = self.sand_pct + self.silt_pct + self.clay_pct

        if abs(total - 100) > 2:
            raise SoilParameterError(
                f"Texture percentages must total approximately 100%. Got {total}."
            )

        validate_number("depth_cm", self.depth_cm, 1, 500)

        if self.bulk_density_g_cm3 is not None:
            validate_number(
                "bulk_density_g_cm3",
                self.bulk_density_g_cm3,
                0.5,
                2.2
            )

        if self.field_capacity is not None:
            validate_number("field_capacity", self.field_capacity, 0.01, 0.8)

        if self.wilting_point is not None:
            validate_number("wilting_point", self.wilting_point, 0.005, 0.7)

        if (
            self.field_capacity is not None
            and self.wilting_point is not None
            and self.field_capacity <= self.wilting_point
        ):
            raise SoilParameterError(
                "Field capacity must exceed wilting point."
            )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]):
        return cls(
            ph=data.get("ph", data.get("soil_ph")),
            organic_carbon_pct=data.get(
                "organic_carbon_pct",
                data.get("soc_pct", data.get("organic_carbon"))
            ),
            sand_pct=data.get("sand_pct", data.get("sand")),
            silt_pct=data.get("silt_pct", data.get("silt")),
            clay_pct=data.get("clay_pct", data.get("clay")),
            depth_cm=data.get("depth_cm", 100),
            bulk_density_g_cm3=data.get("bulk_density_g_cm3"),
            field_capacity=data.get("field_capacity"),
            wilting_point=data.get("wilting_point"),
            source=data.get("source", "user_or_dataset"),
            confidence=data.get("confidence", "medium")
        )

    @property
    def texture_class(self):
        sand = self.sand_pct
        silt = self.silt_pct
        clay = self.clay_pct

        if clay >= 40:
            return "clay"
        if clay >= 27 and sand <= 45:
            return "clay_loam"
        if sand >= 70 and clay < 15:
            return "sandy"
        if sand >= 50 and clay < 20:
            return "sandy_loam"
        if silt >= 50 and clay < 27:
            return "silt_loam"
        if clay >= 20:
            return "loam_or_clay_loam"

        return "loam"

    def to_dict(self):
        result = asdict(self)
        result["texture_class"] = self.texture_class
        return result


TEXTURE_AWC = {
    "sandy": (0.05, 0.10),
    "sandy_loam": (0.08, 0.14),
    "loam": (0.12, 0.18),
    "loam_or_clay_loam": (0.13, 0.19),
    "clay_loam": (0.12, 0.18),
    "clay": (0.10, 0.17),
    "silt_loam": (0.15, 0.21)
}


@dataclass(frozen=True)
class SoilWaterParameters:
    field_capacity: float
    wilting_point: float
    available_water_capacity: float
    total_available_water_mm: float
    readily_available_water_mm: float
    method: str
    confidence: str


def estimate_soil_water_parameters(
    soil,
    root_depth_m=None,
    depletion_fraction=0.5
):
    profile = (
        soil if isinstance(soil, SoilProfile)
        else SoilProfile.from_mapping(soil)
    )

    depletion_fraction = validate_number(
        "depletion_fraction",
        depletion_fraction,
        0.05,
        0.9
    )

    depth = validate_number(
        "root_depth_m",
        root_depth_m if root_depth_m is not None
        else profile.depth_cm / 100,
        0.05,
        3.0
    )

    if (
        profile.field_capacity is not None
        and profile.wilting_point is not None
    ):
        fc = profile.field_capacity
        wp = profile.wilting_point
        method = "measured_or_supplied_fc_wp"
        confidence = profile.confidence

    else:
        low, high = TEXTURE_AWC[profile.texture_class]
        awc = (low + high) / 2

        wp = max(0.03, 0.06 + 0.0012 * profile.clay_pct)
        fc = wp + awc

        method = "texture_based_screening_estimate"
        confidence = "low"

    if fc <= wp:
        raise SoilParameterError("Field capacity must exceed wilting point.")

    awc_fraction = fc - wp
    total_water = awc_fraction * depth * 1000

    return SoilWaterParameters(
        field_capacity=round(fc, 4),
        wilting_point=round(wp, 4),
        available_water_capacity=round(awc_fraction, 4),
        total_available_water_mm=round(total_water, 2),
        readily_available_water_mm=round(
            total_water * depletion_fraction, 2
        ),
        method=method,
        confidence=confidence
    )


def assess_soil_constraints(soil):
    profile = (
        soil if isinstance(soil, SoilProfile)
        else SoilProfile.from_mapping(soil)
    )

    flags = []

    if profile.ph < 5.5:
        flags.append("strong_acidity_screen")
    elif profile.ph < 6.0:
        flags.append("moderate_acidity_screen")
    elif profile.ph > 8.5:
        flags.append("high_alkalinity_screen")

    if profile.organic_carbon_pct < 0.5:
        flags.append("low_organic_carbon_screen")

    if profile.clay_pct > 50:
        flags.append("high_clay_workability_or_drainage_screen")

    if profile.sand_pct > 75:
        flags.append("low_water_retention_screen")

    return {
        "texture_class": profile.texture_class,
        "constraint_flags": flags,
        "screening_only": True,
        "source": profile.source,
        "confidence": profile.confidence
    }