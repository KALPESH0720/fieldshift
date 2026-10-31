from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from app.suggestion_engine.rules.base import BaseRule, RuleDecision

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class CropRepeatGapRule(BaseRule):
    """Require one intervening season before repeating the same crop by default."""

    def __init__(self, minimum_gap_seasons: int = 1) -> None:
        if minimum_gap_seasons < 1:
            raise ValueError("minimum_gap_seasons must be at least one")
        self.minimum_gap_seasons = minimum_gap_seasons

    def evaluate(self, candidate: Mapping[str, Any], context: SuggestionContext) -> RuleDecision:
        name = str(candidate.get("crop_name", "")).strip().casefold()
        gap = max(self.minimum_gap_seasons, int(candidate.get("minimum_repeat_gap_seasons") or 1))
        for previous in context.plot_history:
            previous_name = str(previous.get("crop_name", "")).strip().casefold()
            distance = previous.get("season_distance")
            if previous_name == name and isinstance(distance, int) and distance <= gap:
                return RuleDecision(
                    allowed=False,
                    reason=f"{candidate.get('crop_name')} was grown {distance} season(s) ago; the minimum repeat gap is {gap} season(s).",
                )
        return RuleDecision()

