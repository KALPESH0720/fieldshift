
from __future__ import annotations

import logging
from typing import Any, Callable, Mapping, Sequence

from fieldshift.optimizer.constraints import OptimizationConstraints

from pipelines.p1_grid_layers.pipeline import run_p1_grid_pipeline
from pipelines.p2_simulation.pipeline import run_p2_simulation_pipeline
from pipelines.p3_monitor.pipeline import run_p3_monitor_pipeline
from pipelines.p4_learning.pipeline import run_p4_learning_pipeline
from pipelines.p5_optimizer.pipeline import run_p5_optimizer_pipeline

logger = logging.getLogger("fieldshift.pipeline")


class FieldShiftPipelineError(RuntimeError):
    """Master pipeline execution failure."""


def _find_numeric_score(data: Any) -> float | None:
    """Find a numeric score in simulation output."""

    if isinstance(data, (int, float)):
        return float(data)

    if isinstance(data, Mapping):
        for key in (
            "score",
            "yield_score",
            "suitability_score",
            "crop_score",
            "predicted_yield",
            "yield",
        ):
            value = data.get(key)

            if isinstance(value, (int, float)):
                return float(value)

        for value in data.values():
            result = _find_numeric_score(value)

            if result is not None:
                return result

    return None


def _get_prior_scores(learning_priors: Any) -> dict[str, float]:
    """Extract crop scores from P4 learned priors."""

    if not isinstance(learning_priors, Mapping):
        return {}

    priors = learning_priors.get("priors", learning_priors)

    if not isinstance(priors, Mapping):
        return {}

    scores = {}

    for crop, value in priors.items():
        if isinstance(value, (int, float)):
            scores[str(crop)] = float(value)

        elif isinstance(value, Mapping):
            score = _find_numeric_score(value)

            if score is not None:
                scores[str(crop)] = score

    return scores


def integrate_crop_candidates(
    candidate_data: Sequence[Mapping[str, Any]],
    simulation_results: Sequence[Mapping[str, Any]],
    learning_priors: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """
    Integrate baseline candidate scores, P2 simulation scores,
    and P4 learned prior scores before passing candidates to P5.
    """

    simulation_scores = {}

    for item in simulation_results:
        if not isinstance(item, Mapping):
            continue

        crop = item.get("crop")

        if not crop:
            continue

        simulation_result = item.get("simulation_result")

        score = _find_numeric_score(simulation_result)

        if score is not None:
            simulation_scores[str(crop)] = score

    prior_scores = _get_prior_scores(learning_priors)

    integrated_candidates = []

    for candidate in candidate_data:
        candidate = dict(candidate)

        crop = str(candidate.get("crop", ""))

        baseline_score = float(candidate.get("score", 0.0))

        simulation_score = simulation_scores.get(crop)

        learned_prior = prior_scores.get(crop)

        score_components = [baseline_score]

        if simulation_score is not None:
            score_components.append(simulation_score)

        if learned_prior is not None:
            score_components.append(learned_prior)

        # Average available scores to produce the integrated score.
        integrated_score = sum(score_components) / len(score_components)

        candidate["baseline_score"] = baseline_score
        candidate["simulation_score"] = simulation_score
        candidate["learned_prior"] = learned_prior
        candidate["score"] = integrated_score

        integrated_candidates.append(candidate)

    return integrated_candidates


def run_fieldshift_pipeline(
    grid_input: Mapping[str, Any],
    crops: Sequence[str],
    simulator: Callable[..., Any],
    simulation_config: Mapping[str, Any],
    monitor_checks: Mapping[str, Callable[..., Any]],
    monitor_inputs: Mapping[str, Mapping[str, Any]],
    baseline_scores: Mapping[str, float],
    farmer_feedback: Mapping[str, Sequence[float]],
    candidate_data: Sequence[Mapping[str, Any]],
    optimization_constraints: OptimizationConstraints,
    historical_scores: Sequence[Mapping[str, float]] | None = None,
    historical_outcomes: Sequence[float] | None = None,
    objective: str = "score",
) -> dict[str, Any]:
    """Execute the complete FieldShift P1-P5 pipeline."""

    logger.info("Starting FieldShift pipeline")

    try:
        # P1: Prepare grid layers.
        p1 = run_p1_grid_pipeline(grid_input)

        grid = p1["grid"]

        # P2: Run crop simulations.
        p2 = run_p2_simulation_pipeline(
            grid,
            list(crops),
            simulator,
            simulation_config,
        )

        # P3: Run monitoring checks.
        p3 = run_p3_monitor_pipeline(
            monitor_checks,
            monitor_inputs,
        )

        # P4: Learn crop priors and weights.
        p4 = run_p4_learning_pipeline(
            baseline_scores,
            farmer_feedback,
            historical_scores,
            historical_outcomes,
        )

        # Safely extract P2 simulation results.
        simulation_results = (
            p2.get("results", [])
            if isinstance(p2, Mapping)
            else []
        )

        # Safely extract P4 learning information.
        learning_priors = (
            p4.get("priors", {})
            if isinstance(p4, Mapping)
            else {}
        )

        # Integrate P2 and P4 with crop candidates.
        if simulation_results or learning_priors:
            integrated_candidates = integrate_crop_candidates(
                candidate_data,
                simulation_results,
                learning_priors,
            )
        else:
            integrated_candidates = [
                dict(candidate)
                for candidate in candidate_data
            ]

        # P5: Optimize crop selection using integrated scores.
        p5 = run_p5_optimizer_pipeline(
            integrated_candidates,
            optimization_constraints,
            objective,
        )

        logger.info("FieldShift pipeline completed successfully")

        return {
            "pipeline": "fieldshift",
            "status": "success",
            "grid": p1,
            "simulation": p2,
            "monitoring": p3,
            "learning": p4,
            "optimization": p5,
            
        }

    except Exception as exc:
        logger.exception("FieldShift pipeline execution failed")

        raise FieldShiftPipelineError(
            "FieldShift pipeline execution failed."
        ) from exc
