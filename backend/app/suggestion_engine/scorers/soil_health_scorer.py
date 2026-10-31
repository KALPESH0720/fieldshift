from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.scorers.base import BaseScorer, ScoreResult


class SoilHealthScorer(BaseScorer):
    key = "soil_health"
    weight = 1.0

    def __init__(self, weight: float = 1.0) -> None:
        self.weight = weight

    def score(self, candidate: Mapping[str, Any], context: SuggestionContext) -> ScoreResult:
        reviewed_score = _first_number(candidate, "soil_benefit_score")
        if reviewed_score is not None:
            return ScoreResult(
                score=max(0.0, min(100.0, reviewed_score)),
                reason="Soil-benefit score uses the active reviewed crop rule.",
                metrics={"soil_benefit_score": reviewed_score, "source": candidate.get("soil_benefit_source")},
            )
        nitrogen = _first_number(candidate, "nitrogen_residual", "nitrogen_effect", "nitrogen_contribution")
        organic = _first_number(candidate, "organic_addition", "organic_matter_added", "organic_matter_effect")
        score = 50.0
        if nitrogen is not None:
            score += max(-30.0, min(30.0, nitrogen * 2.0))
        if organic is not None:
            score += max(-20.0, min(20.0, organic * 2.0))
        details = []
        if nitrogen is not None and nitrogen > 0:
            details.append("adds nitrogen to the soil")
        if organic is not None and organic > 0:
            details.append("adds organic matter")
        reason = (
            f"This crop { ' and '.join(details) }." if details
            else "Soil-health benefits are modest or not yet documented."
        )
        return ScoreResult(
            score=max(0.0, min(100.0, score)),
            reason=reason,
            metrics={"nitrogen_effect": nitrogen, "organic_addition": organic},
        )


def _first_number(values: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if values.get(key) is not None:
            return float(values[key])
    return None
