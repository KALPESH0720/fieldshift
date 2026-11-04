"""
FieldShift Optimization Models.

Defines optimization plans, results and objective calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from fieldshift.optimizer.constraints import (
    CropCandidate,
    OptimizationConstraints,
    check_rotation_constraints,
)


@dataclass
class OptimizationPlan:
    selected_crops: list[CropCandidate]
    total_score: float
    total_expected_return: float
    total_water_requirement_mm: float
    feasible: bool
    objective_name: str = "weighted_crop_score"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_crops": [
                {
                    "crop": crop.crop,
                    "score": crop.score,
                    "expected_return": crop.expected_return,
                    "water_requirement_mm": crop.water_requirement_mm,
                    "soil_suitability": crop.soil_suitability,
                    "family": crop.family,
                }
                for crop in self.selected_crops
            ],
            "total_score": self.total_score,
            "total_expected_return": self.total_expected_return,
            "total_water_requirement_mm": self.total_water_requirement_mm,
            "feasible": self.feasible,
            "objective_name": self.objective_name,
            "metadata": self.metadata,
        }


def calculate_plan_score(
    selected_crops: Sequence[CropCandidate],
) -> float:
    """Calculate total recommendation score."""

    return sum(crop.score for crop in selected_crops)


def calculate_plan_return(
    selected_crops: Sequence[CropCandidate],
) -> float:
    """Calculate aggregate expected economic return."""

    return sum(crop.expected_return for crop in selected_crops)


def calculate_plan_water(
    selected_crops: Sequence[CropCandidate],
) -> float:
    """Calculate aggregate water requirement."""

    return sum(
        crop.water_requirement_mm
        for crop in selected_crops
    )


def build_optimization_plan(
    selected_crops: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
    objective_name: str = "weighted_crop_score",
    metadata: dict[str, Any] | None = None,
) -> OptimizationPlan:
    """Construct a plan and evaluate feasibility."""

    crops = list(selected_crops)

    rotation_check = check_rotation_constraints(
        crops, constraints
    )

    total_water = calculate_plan_water(crops)

    water_feasible = (
        total_water <= constraints.available_water_mm
    )

    feasible = (
        rotation_check["feasible"]
        and water_feasible
    )

    return OptimizationPlan(
        selected_crops=crops,
        total_score=calculate_plan_score(crops),
        total_expected_return=calculate_plan_return(crops),
        total_water_requirement_mm=total_water,
        feasible=feasible,
        objective_name=objective_name,
        metadata={
            **(metadata or {}),
            "rotation_constraints": rotation_check,
            "water_feasible": water_feasible,
        },
    )