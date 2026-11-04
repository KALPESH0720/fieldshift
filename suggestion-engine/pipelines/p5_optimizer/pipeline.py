
from __future__ import annotations

from typing import Any, Mapping, Sequence

from fieldshift.optimizer.constraints import (
    CropCandidate,
    OptimizationConstraints,
)
from fieldshift.optimizer.solve import solve_crop_optimization


class OptimizerPipelineError(ValueError):
    """Optimizer pipeline failure."""


def build_crop_candidates(
    candidate_data: Sequence[Mapping[str, Any]],
) -> list[CropCandidate]:
    """Convert structured candidate data into optimizer models."""

    if not candidate_data:
        raise OptimizerPipelineError(
            "Candidate data cannot be empty."
        )

    candidates = []

    for item in candidate_data:

        try:
            candidates.append(
                CropCandidate(
                    crop=str(item["crop"]),
                    score=float(item["score"]),
                    water_requirement_mm=float(
                        item.get("water_requirement_mm", 0)
                    ),
                    soil_suitability=float(
                        item.get("soil_suitability", 1)
                    ),
                    season=str(item.get("season", "")),
                    family=str(item.get("family", "")),
                    root_depth=str(
                        item.get("root_depth", "medium")
                    ),
                    expected_return=float(
                        item.get("expected_return", 0)
                    ),
                    nitrogen_benefit=float(
                        item.get("nitrogen_benefit", 0)
                    ),
                )
            )

        except (KeyError, TypeError, ValueError) as exc:
            raise OptimizerPipelineError(
                f"Invalid candidate data: {item}"
            ) from exc

    return candidates


def optimize_crop_candidates(
    candidate_data: Sequence[Mapping[str, Any]],
    constraints: OptimizationConstraints,
    objective: str = "score",
) -> dict[str, Any]:
    """Run the FieldShift crop optimizer."""

    candidates = build_crop_candidates(
        candidate_data
    )

    result = solve_crop_optimization(
        candidates,
        constraints,
        objective=objective,
        use_fallback=True,
    )

    return result


def run_p5_optimizer_pipeline(
    candidate_data: Sequence[Mapping[str, Any]],
    constraints: OptimizationConstraints,
    objective: str = "score",
) -> dict[str, Any]:
    """Execute P5 crop optimization."""

    result = optimize_crop_candidates(
        candidate_data,
        constraints,
        objective,
    )

    return {
        "stage": "p5_optimizer",
        "status": result["status"],
        "optimization": result,
    }
