from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.rules.base import BaseRule, RuleDecision


class LegumeRotationRule(BaseRule):
    """Give legumes a modest priority after a cereal crop."""

    CEREAL_FAMILIES = {"poaceae", "grass", "cereal", "cereals"}
    LEGUME_FAMILIES = {"fabaceae", "legume", "legumes", "bean", "pulse", "pulses"}

    def evaluate(self, candidate: Mapping[str, Any], context: SuggestionContext) -> RuleDecision:
        if not context.plot_history:
            return RuleDecision()
        previous = context.plot_history[-1]
        previous_family = str(previous.get("crop_family", "")).strip().casefold()
        candidate_family = str(candidate.get("crop_family", "")).strip().casefold()
        previous_name = str(previous.get("crop_name", "")).strip().casefold()
        is_cereal = previous_family in self.CEREAL_FAMILIES or previous_name in {
            "rice", "wheat", "maize", "corn", "barley", "oats", "sorghum", "millet"
        }
        is_legume = candidate_family in self.LEGUME_FAMILIES or bool(candidate.get("is_legume", False))
        if is_cereal and is_legume:
            return RuleDecision(
                reason="A legume after a cereal can help replenish soil nitrogen.",
                priority_adjustment=5.0,
            )
        return RuleDecision()
