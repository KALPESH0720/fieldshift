"""
FieldShift Data and Recommendation Drift Monitoring.

Monitors changes in feature distributions and recommendation
patterns between reference and current datasets.
"""

from __future__ import annotations

from math import isfinite
from statistics import mean, pstdev
from typing import Any, Mapping, Sequence


class DriftDetectionError(ValueError):
    """Raised when drift monitoring inputs are invalid."""


def _validate_numeric(values, name):
    result = []

    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise DriftDetectionError(
                f"{name} must contain numeric values."
            ) from exc

        if not isfinite(number):
            raise DriftDetectionError(
                f"{name} contains a non-finite value."
            )

        result.append(number)

    return result


def _distribution_summary(values):
    if not values:
        return None

    return {
        "count": len(values),
        "mean": mean(values),
        "std": pstdev(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def detect_mean_drift(
    reference_values: Sequence[float],
    current_values: Sequence[float],
    threshold: float = 0.5,
) -> dict[str, Any]:
    """
    Detect mean shift standardized by reference standard deviation.

    threshold = minimum absolute standardized mean difference
    considered meaningful.

    This is a screening metric, not a formal hypothesis test.
    """

    reference = _validate_numeric(
        reference_values, "reference_values"
    )

    current = _validate_numeric(
        current_values, "current_values"
    )

    if len(reference) < 5 or len(current) < 5:
        return {
            "status": "insufficient_data",
            "reference_count": len(reference),
            "current_count": len(current),
        }

    if threshold <= 0:
        raise DriftDetectionError(
            "Threshold must be positive."
        )

    reference_mean = mean(reference)
    current_mean = mean(current)

    reference_std = pstdev(reference)

    if reference_std == 0:
        if current_mean == reference_mean:
            drift_score = 0.0
        else:
            drift_score = float("inf")
    else:
        drift_score = abs(
            current_mean - reference_mean
        ) / reference_std

    drift_detected = drift_score >= threshold

    return {
        "status": (
            "drift_detected"
            if drift_detected
            else "stable"
        ),
        "drift_detected": drift_detected,
        "drift_score": drift_score,
        "threshold": threshold,
        "reference": _distribution_summary(reference),
        "current": _distribution_summary(current),
        "mean_change": round(
            current_mean - reference_mean, 4
        ),
        "interpretation": (
            "The current mean differs from the reference baseline."
            if drift_detected
            else "No meaningful mean shift was detected."
        ),
    }


def detect_feature_drift(
    reference_features: Mapping[str, Sequence[float]],
    current_features: Mapping[str, Sequence[float]],
    threshold: float = 0.5,
) -> dict[str, Any]:
    """
    Evaluate mean drift for multiple features.

    Features can include rainfall, temperature, soil moisture,
    NDVI and other numeric recommendation-engine inputs.
    """

    results = {}

    for feature, reference in reference_features.items():

        if feature not in current_features:
            results[feature] = {
                "status": "missing_current_feature"
            }
            continue

        results[feature] = detect_mean_drift(
            reference,
            current_features[feature],
            threshold,
        )

    return {
        "feature_results": results,
        "features_checked": len(results),
        "drifted_features": [
            feature
            for feature, result in results.items()
            if result.get("drift_detected", False)
        ],
    }


def detect_recommendation_drift(
    reference_recommendations: Sequence[str],
    current_recommendations: Sequence[str],
) -> dict[str, Any]:
    """
    Compare crop recommendation distributions.

    Measures crop frequency changes using total variation distance.
    """

    if not reference_recommendations:
        return {
            "status": "insufficient_reference",
            "drift_score": None,
        }

    if not current_recommendations:
        return {
            "status": "insufficient_current",
            "drift_score": None,
        }

    reference_counts = {}
    current_counts = {}

    for crop in reference_recommendations:
        reference_counts[crop] = (
            reference_counts.get(crop, 0) + 1
        )

    for crop in current_recommendations:
        current_counts[crop] = (
            current_counts.get(crop, 0) + 1
        )

    reference_total = len(reference_recommendations)
    current_total = len(current_recommendations)

    all_crops = (
        set(reference_counts)
        | set(current_counts)
    )

    distance = 0.0

    for crop in all_crops:

        p = (
            reference_counts.get(crop, 0)
            / reference_total
        )

        q = (
            current_counts.get(crop, 0)
            / current_total
        )

        distance += abs(p - q)

    total_variation_distance = distance / 2

    return {
        "status": (
            "distribution_changed"
            if total_variation_distance >= 0.2
            else "distribution_stable"
        ),
        "drift_score": round(
            total_variation_distance, 4
        ),
        "reference_crop_distribution": {
            crop: count / reference_total
            for crop, count in reference_counts.items()
        },
        "current_crop_distribution": {
            crop: count / current_total
            for crop, count in current_counts.items()
        },
        "interpretation": (
            "Crop recommendation frequencies have changed."
            if total_variation_distance >= 0.2
            else "Crop recommendation frequencies remain similar."
        ),
    }


def monitor_model_inputs(
    reference_data: Mapping[str, Sequence[float]],
    current_data: Mapping[str, Sequence[float]],
) -> dict[str, Any]:
    """Convenience function for monitoring multiple model inputs."""

    report = detect_feature_drift(
        reference_data,
        current_data,
    )

    drifted = report["drifted_features"]

    report["overall_status"] = (
        "drift_detected" if drifted else "stable"
    )

    return report