"""
FieldShift Optimization Constraints.

Validates crop candidates and checks agricultural constraints
before crop selection or rotation optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class ConstraintError(ValueError):
    """Raised when optimization constraints are invalid."""


@dataclass(frozen=True)
class CropCandidate:
    crop: str
    score: float
    water_requirement_mm: float = 0.0
    soil_suitability: float = 1.0
    season: str = ""
    family: str = ""
    root_depth: str = "medium"
    expected_return: float = 0.0
    nitrogen_benefit: float = 0.0

    def __post_init__(self):
        if not self.crop.strip():
            raise ConstraintError("Crop name is required.")

        if self.score < 0:
            raise ConstraintError("Score cannot be negative.")

        if self.water_requirement_mm < 0:
            raise ConstraintError("Water requirement cannot be negative.")

        if not 0 <= self.soil_suitability <= 1:
            raise ConstraintError("Soil suitability must be between 0 and 1.")


@dataclass(frozen=True)
class OptimizationConstraints:
    available_water_mm: float
    minimum_soil_suitability: float = 0.3
    maximum_crops: int = 3
    minimum_crop_diversity: int = 1
    forbidden_crops: tuple[str, ...] = ()
    required_crops: tuple[str, ...] = ()
    avoid_same_family_consecutive: bool = True

    def __post_init__(self):
        if self.available_water_mm < 0:
            raise ConstraintError("Available water cannot be negative.")

        if not 0 <= self.minimum_soil_suitability <= 1:
            raise ConstraintError("Minimum soil suitability must be between 0 and 1.")

        if self.maximum_crops < 1:
            raise ConstraintError("Maximum crops must be at least 1.")

        if self.minimum_crop_diversity < 1:
            raise ConstraintError("Minimum diversity must be at least 1.")

        if self.minimum_crop_diversity > self.maximum_crops:
            raise ConstraintError("Minimum diversity cannot exceed maximum crops.")


def validate_candidates(
    candidates: Sequence[CropCandidate],
) -> list[CropCandidate]:
    """Validate and remove duplicate crop names."""

    if not candidates:
        raise ConstraintError("No crop candidates supplied.")

    unique = {}
    for candidate in candidates:
        if not isinstance(candidate, CropCandidate):
            raise ConstraintError("Candidates must be CropCandidate objects.")

        unique.setdefault(candidate.crop.lower(), candidate)

    return list(unique.values())


def check_candidate_constraints(
    candidate: CropCandidate,
    constraints: OptimizationConstraints,
) -> dict[str, Any]:
    """Evaluate individual crop feasibility."""

    flags = []

    if candidate.crop in constraints.forbidden_crops:
        flags.append("crop_forbidden")

    if candidate.water_requirement_mm > constraints.available_water_mm:
        flags.append("water_requirement_exceeded")

    if candidate.soil_suitability < constraints.minimum_soil_suitability:
        flags.append("soil_suitability_below_minimum")

    return {
        "crop": candidate.crop,
        "feasible": len(flags) == 0,
        "constraint_flags": flags,
    }


def check_rotation_constraints(
    selected_crops: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
) -> dict[str, Any]:
    """Check diversity and consecutive crop-family restrictions."""

    flags = []

    crop_names = [crop.crop.lower() for crop in selected_crops]
    families = [
        crop.family.lower()
        for crop in selected_crops
        if crop.family
    ]

    if len(set(crop_names)) < constraints.minimum_crop_diversity:
        flags.append("minimum_crop_diversity_not_met")

    if len(selected_crops) > constraints.maximum_crops:
        flags.append("maximum_crop_count_exceeded")

    if constraints.avoid_same_family_consecutive:
        for first, second in zip(selected_crops, selected_crops[1:]):
            if first.family and second.family:
                if first.family.lower() == second.family.lower():
                    flags.append("same_family_consecutive")
                    break

    missing_required = [
        crop for crop in constraints.required_crops
        if crop.lower() not in crop_names
    ]

    if missing_required:
        flags.append("required_crops_missing")

    return {
        "feasible": len(flags) == 0,
        "constraint_flags": flags,
        "selected_crops": crop_names,
        "crop_families": families,
        "missing_required_crops": missing_required,
    }


def filter_feasible_candidates(
    candidates: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
) -> list[CropCandidate]:
    """Return only individually feasible candidates."""

    validated = validate_candidates(candidates)

    return [
        candidate
        for candidate in validated
        if check_candidate_constraints(
            candidate, constraints
        )["feasible"]
    ]