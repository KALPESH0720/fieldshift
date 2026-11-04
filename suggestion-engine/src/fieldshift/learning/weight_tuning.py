"""
FieldShift Recommendation Weight Tuning.

Tunes recommendation scoring weights using farmer feedback
and observed outcomes.

Includes normalization, bounded updates and safeguards against
unstable weight changes.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence


class WeightTuningError(ValueError):
    """Invalid scoring weights or feedback."""


DEFAULT_WEIGHTS = {
    "soil_benefit": 0.25,
    "economic_return": 0.30,
    "water_fit": 0.20,
    "climate_resilience": 0.15,
    "rotation_benefit": 0.10,
}


def _validate_numeric(value, name):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WeightTuningError(
            f"{name} must be numeric."
        ) from exc

    if not isfinite(number):
        raise WeightTuningError(
            f"{name} must be finite."
        )

    return number


def normalize_weights(
    weights: Mapping[str, float],
) -> dict[str, float]:
    """
    Normalize non-negative scoring weights to sum to 1.
    """

    if not weights:
        raise WeightTuningError(
            "At least one scoring weight is required."
        )

    validated = {}

    for name, value in weights.items():

        number = _validate_numeric(value, name)

        if number < 0:
            raise WeightTuningError(
                f"Weight {name} cannot be negative."
            )

        validated[name] = number

    total = sum(validated.values())

    if total <= 0:
        raise WeightTuningError(
            "At least one weight must be positive."
        )

    return {
        name: round(value / total, 8)
        for name, value in validated.items()
    }


def calculate_weighted_score(
    criteria_scores: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """
    Calculate weighted recommendation score.

    All criterion scores must be normalized to [0, 1].
    """

    normalized_weights = normalize_weights(weights)

    if not criteria_scores:
        raise WeightTuningError(
            "Criterion scores cannot be empty."
        )

    missing = set(normalized_weights) - set(criteria_scores)

    if missing:
        raise WeightTuningError(
            f"Missing criterion scores: {sorted(missing)}"
        )

    score = 0.0

    for criterion, weight in normalized_weights.items():

        value = _validate_numeric(
            criteria_scores[criterion],
            criterion,
        )

        if not 0 <= value <= 1:
            raise WeightTuningError(
                f"{criterion} score must be between 0 and 1."
            )

        score += value * weight

    return round(score, 6)


def tune_weights(
    current_weights: Mapping[str, float],
    criterion_feedback: Mapping[str, float],
    learning_rate: float = 0.05,
    minimum_weight: float = 0.02,
    maximum_weight: float = 0.60,
) -> dict[str, float]:
    """
    Adjust weights based on normalized criterion feedback.

    Feedback values must be between -1 and +1:
        +1 -> increase importance
        -1 -> decrease importance
         0 -> no adjustment

    The update is bounded and normalized after adjustment.
    """

    if not 0 < learning_rate <= 1:
        raise WeightTuningError(
            "Learning rate must be in (0, 1]."
        )

    if not 0 <= minimum_weight < maximum_weight <= 1:
        raise WeightTuningError(
            "Invalid minimum or maximum weight."
        )

    weights = normalize_weights(current_weights)

    if set(criterion_feedback) - set(weights):
        raise WeightTuningError(
            "Feedback contains unknown scoring criteria."
        )

    adjusted = {}

    for criterion, weight in weights.items():

        feedback = _validate_numeric(
            criterion_feedback.get(criterion, 0),
            f"{criterion} feedback",
        )

        if not -1 <= feedback <= 1:
            raise WeightTuningError(
                "Criterion feedback must be between -1 and 1."
            )

        updated = weight * (
            1 + learning_rate * feedback
        )

        updated = max(
            minimum_weight,
            min(maximum_weight, updated),
        )

        adjusted[criterion] = updated

    return normalize_weights(adjusted)


def tune_from_outcomes(
    current_weights: Mapping[str, float],
    historical_scores: Sequence[Mapping[str, float]],
    outcome_scores: Sequence[float],
    learning_rate: float = 0.05,
) -> dict[str, float]:
    """
    Tune weights from historical criterion scores and outcomes.

    Uses criterion-outcome correlation as a feedback signal.
    This is a simple heuristic and is not a causal learning model.
    """

    if len(historical_scores) != len(outcome_scores):
        raise WeightTuningError(
            "Historical scores and outcomes must have equal length."
        )

    if len(outcome_scores) < 5:
        raise WeightTuningError(
            "At least five outcome observations are required."
        )

    outcomes = [
        _validate_numeric(value, "outcome")
        for value in outcome_scores
    ]

    weights = normalize_weights(current_weights)

    feedback = {}

    for criterion in weights:

        values = [
            _validate_numeric(
                row[criterion],
                criterion,
            )
            for row in historical_scores
        ]

        if len(values) != len(outcomes):
            raise WeightTuningError(
                f"Invalid observations for {criterion}."
            )

        x_mean = sum(values) / len(values)
        y_mean = sum(outcomes) / len(outcomes)

        numerator = sum(
            (x - x_mean) * (y - y_mean)
            for x, y in zip(values, outcomes)
        )

        x_variance = sum(
            (x - x_mean) ** 2 for x in values
        )

        y_variance = sum(
            (y - y_mean) ** 2 for y in outcomes
        )

        denominator = (
            x_variance * y_variance
        ) ** 0.5

        correlation = (
            numerator / denominator
            if denominator > 0
            else 0.0
        )

        feedback[criterion] = max(
            -1.0,
            min(1.0, correlation),
        )

    return tune_weights(
        weights,
        feedback,
        learning_rate=learning_rate,
    )


def compare_weight_versions(
    old_weights: Mapping[str, float],
    new_weights: Mapping[str, float],
) -> dict[str, Any]:
    """Compare scoring weight changes."""

    old = normalize_weights(old_weights)
    new = normalize_weights(new_weights)

    if set(old) != set(new):
        raise WeightTuningError(
            "Weight criteria must match."
        )

    changes = {
        criterion: round(
            new[criterion] - old[criterion], 6
        )
        for criterion in old
    }

    return {
        "old_weights": old,
        "new_weights": new,
        "changes": changes,
        "total_absolute_change": round(
            sum(abs(value) for value in changes.values()),
            6,
        ),
    }


def get_default_weights() -> dict[str, float]:
    """Return a copy of the default FieldShift scoring weights."""

    return dict(DEFAULT_WEIGHTS)