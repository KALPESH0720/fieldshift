from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.rules.base import BaseRule, RuleDecision


class CropFamilyRule(BaseRule):
    """Reject a candidate from the same crop family as the latest recorded crop."""

    def evaluate(self, candidate: Mapping[str, Any], context: SuggestionContext) -> RuleDecision:
        history = sorted(context.plot_history, key=lambda record: str(record.get("date", record.get("created_at", ""))))
        previous = history[-1] if history else None
        family = candidate.get("crop_family")
        if previous is None or not family or not previous.get("crop_family"):
            return RuleDecision()
        if str(family).strip().casefold() == str(previous["crop_family"]).strip().casefold():
            previous_name = previous.get("crop_name", "the previous crop")
            return RuleDecision(
                allowed=False,
                reason=f"{candidate.get('crop_name', 'This crop')} is in the {family} family, like {previous_name}; rotate to a different family to reduce carryover risk.",
            )
        return RuleDecision()
