from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.scorers.base import BaseScorer, ScoreResult


class WaterRiskScorer(BaseScorer):
    """Score water resilience higher when demand fits available water."""

    key = "water_risk"
    weight = 1.0

    def __init__(self, weight: float = 1.0) -> None:
        self.weight = weight

    def score(self, candidate: Mapping[str, Any], context: SuggestionContext) -> ScoreResult:
        required = candidate.get("water_requirement_mm", candidate.get("water_required_mm"))
        available = context.available_water_mm
        if not isinstance(required, (int, float)) or available is None:
            return ScoreResult(
                score=50.0,
                reason="Water demand or plot water availability is not recorded.",
                tradeoff="Confirm irrigation or rainfall before planting.",
                metrics={"water_risk": None},
            )
        shortage = max(0.0, float(required) - available)
        risk = min(100.0, shortage / max(float(required), 1.0) * 100.0)
        score = 100.0 - risk
        return ScoreResult(
            score=score,
            reason=(
                "Available water covers the estimated crop need."
                if shortage == 0
                else f"Estimated water need exceeds availability by {shortage:.0f} mm."
            ),
            tradeoff="Plan additional irrigation if rainfall is low." if shortage else None,
            metrics={"water_risk": risk, "water_shortage_mm": shortage},
        )
