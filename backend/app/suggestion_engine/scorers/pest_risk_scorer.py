from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.scorers.base import BaseScorer, ScoreResult


class PestRiskScorer(BaseScorer):
    """Reward a break in host-crop/family continuity from plot history."""

    key = "pest_risk"
    weight = 1.0

    def __init__(self, carryover_penalty: float = 35.0, host_penalty: float = 20.0, weight: float = 1.0):
        self.carryover_penalty = carryover_penalty
        self.host_penalty = host_penalty
        self.weight = weight

    def score(self, candidate: Mapping[str, Any], context: SuggestionContext) -> ScoreResult:
        baseline = candidate.get("baseline_pest_risk")
        if baseline is None:
            return ScoreResult(
                score=50.0,
                reason="Reviewed pest-risk data is missing; this component is unscored.",
                tradeoff="Ask a local advisor to review pest and disease history.",
                metrics={"pest_risk": None, "known": False},
            )
        risk = float(baseline)
        candidate_family = str(candidate.get("crop_family", "")).strip().casefold()
        candidate_name = str(candidate.get("crop_name", "")).strip().casefold()
        history = list(context.plot_history)
        previous = history[-1] if history else {}
        previous_family = str(previous.get("crop_family", "")).strip().casefold()
        previous_name = str(previous.get("crop_name", "")).strip().casefold()
        reasons = []
        if candidate_family and candidate_family == previous_family:
            risk += self.carryover_penalty
            reasons.append("the same crop family was grown most recently")

        host_names = {str(value).strip().casefold() for value in (candidate.get("host_crops") or ())}
        host_families = {str(value).strip().casefold() for value in (candidate.get("host_crop_families") or ())}
        history_names = {str(row.get("crop_name", "")).strip().casefold() for row in history}
        history_families = {str(row.get("crop_family", "")).strip().casefold() for row in history}
        pest_rules = list(candidate.get("pest_host_rule_records") or ())
        matching_rules = [
            rule for rule in pest_rules
            if ({str(v).strip().casefold() for v in rule.get("host_crops", ())} & history_names)
            or ({str(v).strip().casefold() for v in rule.get("host_families", ())} & history_families)
        ]
        if pest_rules:
            for pest_rule in matching_rules:
                risk += float(pest_rule.get("risk_points", self.host_penalty))
            if matching_rules:
                names = ", ".join(str(item.get("pest_name", "pest")) for item in matching_rules)
                reasons.append(f"recorded host crops are associated with {names}")
        elif (host_names & history_names) or (host_families & history_families):
            # Backward-compatible fallback until region-specific reviewed records exist.
            risk += self.host_penalty
            reasons.append("recent crops can host pests that affect this crop")
        risk = max(risk, float(baseline))
        risk = max(0.0, min(100.0, risk))
        reason = (
            "Pest carryover risk is higher because " + " and ".join(reasons) + "."
            if reasons else "Recent crop history shows low pest carryover risk."
        )
        tradeoff = "Monitor for pests after planting." if risk >= 35 else None
        return ScoreResult(
            score=100.0 - risk,
            reason=reason,
            tradeoff=tradeoff,
            metrics={"pest_risk": risk, "crop_name": candidate_name,
                     "knowledge_record_ids": [item.get("id") for item in pest_rules],
                     "matching_pest_record_ids": [item.get("id") for item in matching_rules],
                     "reviewed_pest_knowledge": bool(pest_rules)},
        )
