"""Composable crop recommendation pipeline."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from app.schemas.suggestion import OptionCard, RecommendationResponse
from app.suggestion_engine.explainers.reason_builder import ReasonBuilder
from app.suggestion_engine.filters.base import BaseFilter
from app.suggestion_engine.rules.base import BaseRule, RuleDecision
from app.suggestion_engine.scorers.base import BaseScorer, ScoreResult


@dataclass(frozen=True)
class SuggestionContext:
    """Shared plot, history, soil, market, and request data passed to components."""

    plot_id: int
    season: str
    region: str | None = None
    plot_history: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    soil_data: Mapping[str, Any] | None = None
    market_prices: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    available_water_mm: float | None = None
    preferred_crops: Sequence[str] = field(default_factory=tuple)
    plot_area_acres: float = 1.0
    soil_type: str | None = None
    rainfall_mm: float | None = None
    forecast_rainfall_mm: float | None = None
    sowing_window_days_remaining: int | None = None
    irrigation_type: str | None = None
    farmer_preferences: Sequence[str] = field(default_factory=tuple)


class PipelineOrchestrator:
    """Runs candidate filters, agronomic rules, weighted scorers, and explanations."""

    def __init__(
        self,
        filters: Sequence[BaseFilter] = (),
        rules: Sequence[BaseRule] = (),
        scorers: Sequence[BaseScorer] = (),
        reason_builder: ReasonBuilder | None = None,
    ) -> None:
        self.filters = tuple(filters)
        self.rules = tuple(rules)
        self.scorers = tuple(scorers)
        self.reason_builder = reason_builder or ReasonBuilder()
        for scorer in self.scorers:
            if not isfinite(scorer.weight) or scorer.weight <= 0:
                raise ValueError(f"Scorer {scorer.key!r} must have a finite positive weight")

    def run(
        self,
        *,
        plot_id: int,
        season: str,
        region: str | None = None,
        candidates: Sequence[Mapping[str, Any]],
        plot_history: Sequence[Mapping[str, Any]] = (),
        soil_data: Mapping[str, Any] | None = None,
        market_prices: Sequence[Mapping[str, Any]] = (),
        available_water_mm: float | None = None,
        preferred_crops: Sequence[str] = (),
        limit: int = 3,
        plot_area_acres: float = 1.0,
        data_quality_notes: Sequence[str] = (),
        advisor_referral_required: bool = False,
        advisor_referral_reason: str | None = None,
        soil_type: str | None = None,
        rainfall_mm: float | None = None,
        forecast_rainfall_mm: float | None = None,
        sowing_window_days_remaining: int | None = None,
        irrigation_type: str | None = None,
        farmer_preferences: Sequence[str] = (),
        ruleset_version: str = "ruleset-v1",
        scorer_version: str = "weighted-v1",
    ) -> RecommendationResponse:
        """Create ranked option cards using the injected domain components."""
        if plot_id <= 0:
            raise ValueError("plot_id must be positive")
        if limit <= 0:
            raise ValueError("limit must be positive")
        context = SuggestionContext(
            plot_id=plot_id,
            season=season,
            region=region,
            plot_history=plot_history,
            soil_data=soil_data,
            market_prices=market_prices,
            available_water_mm=available_water_mm,
            preferred_crops=preferred_crops,
            plot_area_acres=plot_area_acres,
            soil_type=soil_type,
            rainfall_mm=rainfall_mm,
            forecast_rainfall_mm=forecast_rainfall_mm,
            sowing_window_days_remaining=sowing_window_days_remaining,
            irrigation_type=irrigation_type,
            farmer_preferences=farmer_preferences,
        )

        filtered: list[Mapping[str, Any]] = list(candidates)
        for candidate_filter in self.filters:
            filtered = list(candidate_filter.apply(filtered, context))

        cards: list[tuple[float, int, OptionCard]] = []
        preferred_names = {str(name).casefold() for name in context.preferred_crops}

        for index, candidate in enumerate(filtered):
            rule_reasons: list[str] = []
            priority_adjustment = 0.0
            rejected = False
            for rule in self.rules:
                decision = rule.evaluate(candidate, context)
                if isinstance(decision, bool):
                    decision = RuleDecision(allowed=decision)
                if not decision.allowed:
                    rejected = True
                    if decision.reason:
                        rule_reasons.append(decision.reason)
                    break
                if decision.reason:
                    rule_reasons.append(decision.reason)
                priority_adjustment += decision.priority_adjustment
            if rejected:
                continue

            score_results: dict[str, ScoreResult] = {}
            weighted_total = 0.0
            total_weight = 0.0
            for scorer in self.scorers:
                raw_result = scorer.score(candidate, context)
                result = raw_result if isinstance(raw_result, ScoreResult) else ScoreResult(score=float(raw_result))
                if not isfinite(result.score) or not 0 <= result.score <= 100:
                    raise ValueError(f"Scorer {scorer.key!r} returned a score outside 0–100")
                score_results[scorer.key] = result
                weighted_total += result.score * scorer.weight
                total_weight += scorer.weight
            overall_score = weighted_total / total_weight if total_weight else 0.0
            overall_score = min(100.0, max(0.0, overall_score + priority_adjustment))

            crop_name = str(candidate.get("crop_name", candidate.get("name", ""))).strip()
            if not crop_name:
                raise ValueError("Each crop candidate must include crop_name or name")
            reasons, tradeoffs = self.reason_builder.build(
                crop_name,
                score_results,
                rule_reasons,
                preferred=crop_name.casefold() in preferred_names,
            )
            metrics = {key: result.metrics for key, result in score_results.items()}
            expected_return = candidate.get("expected_net_return", candidate.get("net_return"))
            if expected_return is None:
                expected_return = next(
                    (item.get("expected_net_return", item.get("net_return")) for item in metrics.values()
                     if item.get("expected_net_return", item.get("net_return")) is not None),
                    None,
                )
            card = OptionCard(
                crop_name=crop_name,
                score=round(overall_score, 2),
                expected_yield_kg=candidate.get("expected_yield_kg", candidate.get("expected_yield")),
                expected_net_return=expected_return,
                soil_health_score=self._score_value(score_results, "soil_health"),
                pest_risk_score=self._score_value(score_results, "pest_risk"),
                water_risk_score=self._score_value(score_results, "water_risk"),
                reasons=reasons,
                tradeoffs=tradeoffs,
                score_components={key: round(value.score, 2) for key, value in score_results.items()},
                source_ids=list(candidate.get("source_ids", [])),
                source_citations=list(candidate.get("source_citations", [])),
                freshness=dict(candidate.get("freshness", {})),
                assumptions=list(candidate.get("assumptions", [])),
                confidence=candidate.get("confidence", "low"),
                preference_matches=self._preference_matches(candidate, context.farmer_preferences),
                benefit=self._benefit(score_results, crop_name),
                tradeoff=(tradeoffs[0] if tradeoffs else "Confirm local costs and conditions with an advisor before planting."),
            )
            cards.append((overall_score, index, card))

        cards.sort(key=lambda item: (-item[0], item[1]))
        if "high_return" in context.farmer_preferences:
            return_options = [item for item in cards if item[2].expected_net_return is not None]
            if return_options:
                best_return = max(return_options, key=lambda item: item[2].expected_net_return)[2]
                best_return.preference_matches.append("high_return")
        return RecommendationResponse(
            plot_id=plot_id,
            season=season,
            generated_at=datetime.now(UTC),
            ruleset_version=ruleset_version,
            scorer_version=scorer_version,
            scoring_weights={scorer.key: scorer.weight for scorer in self.scorers},
            options=[card for _, _, card in cards[:limit]],
            advisor_referral_required=advisor_referral_required,
            advisor_referral_reason=advisor_referral_reason,
            data_quality_notes=list(data_quality_notes),
        )

    @staticmethod
    def _benefit(scores: Mapping[str, ScoreResult], crop_name: str) -> str:
        for key in ("soil_health", "water_risk", "pest_risk", "net_return"):
            result = scores.get(key)
            if result and result.reason:
                return result.reason
        return f"{crop_name} passed the available screening checks."

    @staticmethod
    def _score_value(scores: Mapping[str, ScoreResult], key: str) -> float | None:
        result = scores.get(key)
        return round(result.score, 2) if result else None

    @staticmethod
    def _preference_matches(candidate: Mapping[str, Any], preferences: Sequence[str]) -> list[str]:
        matches: list[str] = []
        water = str(candidate.get("water_requirement", "")).casefold()
        if "low_water" in preferences and water in {"low", "very low"}:
            matches.append("low_water")
        if "early_cash" in preferences and candidate.get("duration_days") is not None and int(candidate["duration_days"]) <= 90:
            matches.append("early_cash")
        if "soil_health" in preferences and float(candidate.get("soil_benefit_score") or 0) >= 60:
            matches.append("soil_health")
        return matches
