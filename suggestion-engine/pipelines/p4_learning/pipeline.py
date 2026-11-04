
from __future__ import annotations

from typing import Any, Mapping, Sequence

from fieldshift.learning.prior import (
    build_priors,
    update_priors_from_feedback,
    rank_crop_priors,
)
from fieldshift.learning.weight_tuning import (
    get_default_weights,
    tune_from_outcomes,
    compare_weight_versions,
)

class LearningPipelineError(ValueError):
    """Learning pipeline failure."""

def run_prior_learning(
    baseline_scores: Mapping[str, float],
    feedback: Mapping[str, Sequence[float]],
    confidence: float = 0.5,
) -> dict[str, Any]:
    """Build baseline crop priors and update them with feedback."""

    if not baseline_scores:
        raise LearningPipelineError(
            "Baseline crop scores are required."
        )

    priors = build_priors(
        baseline_scores,
        confidence=confidence,
    )

    updated = update_priors_from_feedback(
        priors,
        feedback,
    )

    return {
        "priors": updated,
        "ranked_priors": rank_crop_priors(updated),
    }

def run_weight_learning(
    historical_scores: Sequence[Mapping[str, float]],
    outcomes: Sequence[float],
    current_weights: Mapping[str, float] | None = None,
    learning_rate: float = 0.05,
) -> dict[str, Any]:
    """Tune scoring weights from historical recommendation outcomes."""

    old_weights = dict(
        current_weights or get_default_weights()
    )

    new_weights = tune_from_outcomes(
        old_weights,
        historical_scores,
        outcomes,
        learning_rate,
    )

    comparison = compare_weight_versions(
        old_weights,
        new_weights,
    )

    return {
        "old_weights": old_weights,
        "new_weights": new_weights,
        "comparison": comparison,
    }

def run_p4_learning_pipeline(
    baseline_scores: Mapping[str, float],
    feedback: Mapping[str, Sequence[float]],
    historical_scores: Sequence[Mapping[str, float]] | None = None,
    outcomes: Sequence[float] | None = None,
    current_weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Execute P4 learning."""

    prior_result = run_prior_learning(
        baseline_scores,
        feedback,
    )

    weight_result = None

    if historical_scores and outcomes:
        weight_result = run_weight_learning(
            historical_scores,
            outcomes,
            current_weights,
        )

    return {
        "stage": "p4_learning",
        "status": "success",
        "priors": prior_result,
        "weights": weight_result,
    }
