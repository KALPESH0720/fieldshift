"""
FieldShift Greedy Optimization Fallback.

Greedy crop selection using score efficiency, water constraints,
crop diversity and rotation restrictions.
"""

from __future__ import annotations

from typing import Any, Sequence

from fieldshift.optimizer.constraints import (
    CropCandidate,
    OptimizationConstraints,
    check_candidate_constraints,
    check_rotation_constraints,
    validate_candidates,
)
from fieldshift.optimizer.model import build_optimization_plan


def _selection_objective(
    candidate: CropCandidate,
    water_penalty: float = 0.0,
) -> float:
    """Score candidate using recommendation quality and water cost."""

    return (
        candidate.score
        + candidate.expected_return * 0.001
        - candidate.water_requirement_mm * water_penalty
    )


def greedy_select_crops(
    candidates: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
) -> list[CropCandidate]:
    """
    Greedily select crops under water and rotation constraints.

    This is a heuristic, not a guaranteed global optimum.
    """

    validated = validate_candidates(candidates)

    feasible_candidates = [
        crop for crop in validated
        if check_candidate_constraints(
            crop, constraints
        )["feasible"]
    ]

    ranked = sorted(
        feasible_candidates,
        key=lambda crop: _selection_objective(
            crop,
            water_penalty=0.0001,
        ),
        reverse=True,
    )

    selected = []
    used_water = 0.0

    for candidate in ranked:

        if len(selected) >= constraints.maximum_crops:
            break

        if (
            used_water + candidate.water_requirement_mm
            > constraints.available_water_mm
        ):
            continue

        trial = selected + [candidate]

        rotation_check = check_rotation_constraints(
            trial, constraints
        )

        # Required crops may be absent until the final selection.
        temporary_flags = [
            flag for flag in rotation_check["constraint_flags"]
            if flag != "required_crops_missing"
        ]

        if temporary_flags:
            continue

        selected.append(candidate)
        used_water += candidate.water_requirement_mm

    return selected


def run_greedy_fallback(
    candidates: Sequence[CropCandidate],
    constraints: OptimizationConstraints,
) -> dict[str, Any]:
    """Run fallback and return a structured optimization result."""

    selected = greedy_select_crops(
        candidates,
        constraints,
    )

    plan = build_optimization_plan(
        selected,
        constraints,
        objective_name="greedy_fallback",
        metadata={
            "solver": "greedy",
            "optimality_guaranteed": False,
        },
    )

    return {
        "solver": "greedy_fallback",
        "status": (
            "feasible"
            if plan.feasible
            else "infeasible_or_partial"
        ),
        "plan": plan.to_dict(),
        "selected_count": len(selected),
        "candidate_count": len(candidates),
        "optimality_guaranteed": False,
    }