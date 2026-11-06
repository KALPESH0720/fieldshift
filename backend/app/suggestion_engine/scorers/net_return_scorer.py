from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from math import tanh

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.scorers.base import BaseScorer, ScoreResult


class NetReturnScorer(BaseScorer):
    key = "net_return"
    weight = 1.0

    def __init__(self, score_scale: float = 100_000.0, weight: float = 1.0) -> None:
        if score_scale <= 0:
            raise ValueError("score_scale must be positive")
        self.score_scale = score_scale
        self.weight = weight

    def score(self, candidate: Mapping[str, Any], context: SuggestionContext) -> ScoreResult:
        yield_per_acre = _number(candidate, "expected_yield_kg_per_acre")
        expected_yield = (
            yield_per_acre * context.plot_area_acres if yield_per_acre is not None
            else _number(candidate, "expected_yield_kg", "expected_yield", "yield_kg")
        )
        expected_price = _number(candidate, "expected_price", "modal_price")
        if expected_price is None:
            name = str(candidate.get("crop_name", "")).casefold()
            market_match = next(
                (price for price in context.market_prices if str(price.get("crop_name", "")).casefold() == name),
                None,
            )
            if market_match:
                expected_price = _number(market_match, "modal_price", "price")

        if expected_yield is None or expected_price is None:
            return ScoreResult(
                score=50.0,
                reason="Expected yield or market price is missing, so returns are uncertain.",
                tradeoff="Check local yield and mandi price estimates before choosing.",
            )

        input_cost_per_acre = _number(candidate, "input_cost_inr_per_acre")
        legacy_cost = _number(candidate, "input_costs", "input_cost", "cost")
        input_cost_known = input_cost_per_acre is not None or legacy_cost is not None
        input_cost = input_cost_per_acre * context.plot_area_acres if input_cost_per_acre is not None else (legacy_cost or 0.0)
        eligible_subsidy = _number(candidate, "eligible_subsidy_inr_per_acre")
        legacy_subsidy = _number(candidate, "subsidies", "subsidy")
        subsidy_known = (
            candidate.get("subsidy_eligible") is False
            or (candidate.get("subsidy_eligible") is True and eligible_subsidy is not None)
            or legacy_subsidy is not None
        )
        subsidy = (
            eligible_subsidy * context.plot_area_acres
            if candidate.get("subsidy_eligible") is True and eligible_subsidy is not None
            else (legacy_subsidy or 0.0)
        )
        fertilizer_per_acre = _number(candidate, "fertilizer_savings_inr_per_acre")
        legacy_fertilizer = _number(candidate, "fertilizer_reductions", "fertilizer_reduction")
        fertilizer_known = fertilizer_per_acre is not None or legacy_fertilizer is not None
        fertilizer_reduction = (
            fertilizer_per_acre * context.plot_area_acres if fertilizer_per_acre is not None
            else (legacy_fertilizer or 0.0)
        )
        missing = []
        if expected_yield is None:
            missing.append("expected yield")
        if expected_price is None:
            missing.append("fresh market price")
        if not input_cost_known:
            missing.append("input cost")
        if not fertilizer_known:
            missing.append("fertilizer savings")
        if not subsidy_known:
            missing.append("subsidy eligibility")
        if missing:
            return ScoreResult(
                score=50.0,
                reason="Net return is unavailable because " + ", ".join(missing) + " data is missing.",
                tradeoff="Confirm missing yield, price, cost, fertilizer, and subsidy details before comparing returns.",
                metrics={"expected_net_return": None, "missing_assumptions": missing},
            )
        net_return = expected_yield * expected_price - input_cost + subsidy + fertilizer_reduction
        score = 50.0 + 50.0 * tanh(net_return / self.score_scale)
        return ScoreResult(
            score=score,
            reason=f"Estimated net return is {net_return:,.0f} before unlisted costs.",
            metrics={
                "expected_net_return": round(net_return, 2),
                "currency": candidate.get("currency", "INR"),
                "yield_kg": round(expected_yield, 3),
                "yield_kg_per_acre": yield_per_acre,
                "price_per_kg": expected_price,
                "input_cost_total": round(input_cost, 2),
                "fertilizer_savings_total": round(fertilizer_reduction, 2),
                "eligible_subsidy_total": round(subsidy, 2),
                "plot_area_acres": context.plot_area_acres,
                "price_source": candidate.get("price_source"),
                "price_date": candidate.get("price_date"),
            },
        )


def _number(values: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = values.get(key)
        if value is not None:
            return float(value)
    return None
