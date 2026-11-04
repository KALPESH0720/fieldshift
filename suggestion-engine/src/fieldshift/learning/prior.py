"""
FieldShift Crop Prior Learning.

Builds crop suitability priors from expert knowledge and
historical farmer outcomes.

Priors are initial suitability estimates, not final recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence


class PriorError(ValueError):
    """Invalid crop prior or feedback data."""


def _validate_score(value: float, name: str = "score") -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise PriorError(f"{name} must be numeric.") from exc

    if not isfinite(value) or not 0 <= value <= 1:
        raise PriorError(f"{name} must be between 0 and 1.")

    return value


def _validate_positive(value: float, name: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise PriorError(f"{name} must be numeric.") from exc

    if not isfinite(value) or value <= 0:
        raise PriorError(f"{name} must be positive.")

    return value


@dataclass(frozen=True)
class CropPrior:
    crop: str
    suitability: float
    confidence: float = 0.5
    evidence_count: int = 0
    source: str = "expert_or_baseline"

    def __post_init__(self):
        if not self.crop.strip():
            raise PriorError("Crop name is required.")

        _validate_score(self.suitability, "suitability")
        _validate_score(self.confidence, "confidence")

        if self.evidence_count < 0:
            raise PriorError("Evidence count cannot be negative.")


def build_crop_prior(
    crop: str,
    suitability: float,
    confidence: float = 0.5,
    source: str = "expert_or_baseline",
) -> CropPrior:
    """Create a validated initial crop suitability prior."""

    return CropPrior(
        crop=crop.strip(),
        suitability=_validate_score(suitability),
        confidence=_validate_score(confidence, "confidence"),
        source=source,
    )


def build_priors(
    crop_scores: Mapping[str, float],
    confidence: float = 0.5,
    source: str = "expert_or_baseline",
) -> dict[str, CropPrior]:
    """Build priors for multiple crops."""

    if not crop_scores:
        raise PriorError("At least one crop score is required.")

    return {
        crop: build_crop_prior(
            crop,
            score,
            confidence,
            source,
        )
        for crop, score in crop_scores.items()
    }


def update_crop_prior(
    prior: CropPrior,
    observed_outcomes: Sequence[float],
    evidence_strength: float = 1.0,
) -> CropPrior:
    """
    Update a crop prior using farmer outcomes.

    Outcomes must be normalized to [0, 1].
    The update is a weighted mean, not a full Bayesian posterior.
    """

    outcomes = [
        _validate_score(value, "observed outcome")
        for value in observed_outcomes
    ]

    strength = _validate_positive(
        evidence_strength,
        "evidence_strength",
    )

    if not outcomes:
        return prior

    prior_weight = max(
        1.0,
        prior.confidence * max(prior.evidence_count, 1),
    )

    evidence_weight = len(outcomes) * strength

    updated_score = (
        prior.suitability * prior_weight
        + sum(outcomes) * strength
    ) / (prior_weight + evidence_weight)

    updated_evidence_count = (
        prior.evidence_count + len(outcomes)
    )

    confidence = min(
        0.99,
        1 - 1 / (updated_evidence_count + 2),
    )

    return CropPrior(
        crop=prior.crop,
        suitability=round(updated_score, 4),
        confidence=round(confidence, 4),
        evidence_count=updated_evidence_count,
        source="updated_with_farmer_feedback",
    )


def update_priors_from_feedback(
    priors: Mapping[str, CropPrior],
    feedback: Mapping[str, Sequence[float]],
) -> dict[str, CropPrior]:
    """Update available crop priors using crop-specific feedback."""

    updated = dict(priors)

    for crop, outcomes in feedback.items():

        if crop not in priors:
            updated[crop] = build_crop_prior(
                crop,
                suitability=0.5,
                confidence=0.2,
                source="feedback_only_initialization",
            )

        updated[crop] = update_crop_prior(
            updated[crop],
            outcomes,
        )

    return updated


def rank_crop_priors(
    priors: Mapping[str, CropPrior],
) -> list[dict[str, Any]]:
    """Rank crop priors by suitability."""

    ranked = sorted(
        priors.values(),
        key=lambda item: item.suitability,
        reverse=True,
    )

    return [
        {
            "rank": index + 1,
            "crop": prior.crop,
            "suitability_prior": prior.suitability,
            "confidence": prior.confidence,
            "evidence_count": prior.evidence_count,
            "source": prior.source,
        }
        for index, prior in enumerate(ranked)
    ]


def prior_to_dict(prior: CropPrior) -> dict[str, Any]:
    """Serialize a prior for storage or API responses."""

    return {
        "crop": prior.crop,
        "suitability": prior.suitability,
        "confidence": prior.confidence,
        "evidence_count": prior.evidence_count,
        "source": prior.source,
    }