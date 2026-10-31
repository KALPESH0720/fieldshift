from collections.abc import Mapping
from typing import Any

from app.suggestion_engine.scorers.base import ScoreResult


class ReasonBuilder:
    """Turns component output into concise language suitable for farmer-facing cards."""

    _DEFAULT_REASONS = {
        "net_return": "This option has a promising expected return.",
        "soil_health": "This crop may support soil health.",
        "pest_risk": "The crop rotation has a manageable pest risk.",
        "water_risk": "Water needs appear manageable for this plot.",
    }

    def build(
        self,
        crop_name: str,
        scores: Mapping[str, ScoreResult],
        rule_reasons: list[str] | None = None,
        preferred: bool = False,
    ) -> tuple[list[str], list[str]]:
        reasons: list[str] = []
        tradeoffs: list[str] = []
        if preferred:
            reasons.append("This crop matches your stated preference.")
        if rule_reasons:
            reasons.extend(rule_reasons)
        for key, result in scores.items():
            reason = result.reason or self._DEFAULT_REASONS.get(key)
            if reason:
                reasons.append(reason)
            if result.tradeoff:
                tradeoffs.append(result.tradeoff)

        if not reasons:
            reasons.append(f"{crop_name} passed the available checks for this plot and season.")
        # Preserve order while removing duplicate rationale from multiple components.
        return list(dict.fromkeys(reasons)), list(dict.fromkeys(tradeoffs))


def build_reasons(
    crop_name: str,
    scores: Mapping[str, ScoreResult],
    rule_reasons: list[str] | None = None,
    preferred: bool = False,
) -> tuple[list[str], list[str]]:
    return ReasonBuilder().build(crop_name, scores, rule_reasons, preferred)
