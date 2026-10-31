from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.rules.base import BaseRule, RuleDecision


class RootDepthRule(BaseRule):
    """Encourage alternating shallow- and deep-rooted crops across seasons."""

    def evaluate(self, candidate: Mapping[str, Any], context: SuggestionContext) -> RuleDecision:
        history = sorted(context.plot_history, key=lambda record: str(record.get("date", record.get("created_at", ""))))
        previous = history[-1] if history else None
        depth = candidate.get("root_depth")
        previous_depth = previous.get("root_depth") if previous else None
        if not depth or not previous_depth:
            return RuleDecision()
        if str(depth).strip().casefold() == str(previous_depth).strip().casefold():
            return RuleDecision(
                allowed=False,
                reason=f"Choose a different root depth from the previous {previous.get('crop_name', 'crop')} to alternate soil nutrient zones.",
            )
        return RuleDecision()
