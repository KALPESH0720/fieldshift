"""
FieldShift Crop Optimization Solver.

Searches feasible crop combinations to maximize crop recommendation
scores while respecting water, diversity and rotation constraints.

Uses exact combination search for smaller problems and greedy
fallback for larger problems.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any, Sequence

from fieldshift.optimizer.constraints import (
    CropCandidate,
    OptimizationConstraints,
    check_candidate_constraints,
    check_rotation_constraints,
    validate_candidates,
)
from fieldshift.optimizer.model import build_optimization_plan
from fieldshift.optimizer.greedy_fallback import (
    run_greedy_fallback,
)


class OptimizationError(ValueError):
    """Raised when optimization cannot be performed."""


def _required_crops_present(
    selected: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
) -> bool:
    selected_names = {
        crop.crop.lower()
        for crop in selected
    }

    return all(
        crop.lower() in selected_names
        for crop in constraints.required_crops
    )


def _combination_is_feasible(
    selected: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
) -> bool:
    """Check all constraints for a crop combination."""

    if not selected:
        return False

    if len(selected) > constraints.maximum_crops:
        return False

    total_water = sum(
        crop.water_requirement_mm
        for crop in selected
    )

    if total_water > constraints.available_water_mm:
        return False

    if not _required_crops_present(
        selected, constraints
    ):
        return False

    rotation = check_rotation_constraints(
        selected, constraints
    )

    if not rotation["feasible"]:
        return False

    for crop in selected:

        check = check_candidate_constraints(
            crop, constraints
        )

        if not check["feasible"]:
            return False

    return True


def _objective_value(
    selected: Sequence[CropCandidate],
    objective: str,
) -> float:
    """Calculate objective for a crop combination."""

    if objective == "score":
        return sum(crop.score for crop in selected)

    if objective == "economic_return":
        return sum(
            crop.expected_return
            for crop in selected
        )

    if objective == "soil_benefit":
        return sum(
            crop.nitrogen_benefit
            for crop in selected
        )

    if objective == "balanced":
        return sum(
            crop.score
            + crop.expected_return * 0.001
            + crop.nitrogen_benefit * 0.1
            for crop in selected
        )

    raise OptimizationError(
        f"Unknown objective: {objective}"
    )


def solve_exact(
    candidates: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
    objective: str = "score",
    maximum_search_candidates: int = 20,
) -> dict[str, Any]:
    """
    Search all crop combinations up to maximum_crops.

    This produces the best feasible combination for the selected
    objective among the combinations examined.
    """

    validated = validate_candidates(candidates)

    if len(validated) > maximum_search_candidates:
        raise OptimizationError(
            "Candidate count exceeds exact-search limit."
        )

    individually_feasible = [
        crop for crop in validated
        if check_candidate_constraints(
            crop, constraints
        )["feasible"]
    ]

    best_selection = None
    best_objective = float("-inf")
    combinations_checked = 0

    maximum_size = min(
        constraints.maximum_crops,
        len(individually_feasible),
    )

    for size in range(
        constraints.minimum_crop_diversity,
        maximum_size + 1,
    ):

        for combination in combinations(
            individually_feasible,
            size,
        ):

            combinations_checked += 1

            if not _combination_is_feasible(
                combination, constraints
            ):
                continue

            value = _objective_value(
                combination, objective
            )

            if value > best_objective:
                best_objective = value
                best_selection = list(combination)

    if best_selection is None:

        return {
            "solver": "exact",
            "status": "infeasible",
            "plan": None,
            "combinations_checked": combinations_checked,
            "message": (
                "No feasible crop combination was found."
            ),
        }

    plan = build_optimization_plan(
        best_selection,
        constraints,
        objective_name=objective,
        metadata={
            "solver": "exact",
            "combinations_checked": combinations_checked,
            "objective_value": best_objective,
            "optimality_guaranteed": True,
        },
    )

    return {
        "solver": "exact",
        "status": "optimal",
        "plan": plan.to_dict(),
        "combinations_checked": combinations_checked,
        "objective_value": best_objective,
        "optimality_guaranteed": True,
    }


def solve_crop_optimization(
    candidates: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
    objective: str = "score",
    maximum_search_candidates: int = 20,
    use_fallback: bool = True,
) -> dict[str, Any]:
    """
    Main optimization entry point.

    Exact optimization is preferred for small candidate sets.
    Greedy fallback is used when exact search is too large.
    """

    validated = validate_candidates(candidates)

    try:

        result = solve_exact(
            validated,
            constraints,
            objective=objective,
            maximum_search_candidates=maximum_search_candidates,
        )

        if result["status"] == "optimal":
            return result

        if not use_fallback:
            return result

    except OptimizationError:

        if not use_fallback:
            raise

    fallback = run_greedy_fallback(
        validated,
        constraints,
    )

    fallback["fallback_reason"] = (
        "Exact search exceeded its limit or found no feasible plan."
    )

    return fallback