from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.scorers import NetReturnScorer, PestRiskScorer, SoilHealthScorer


def test_net_return_applies_costs_subsidies_and_fertilizer_savings():
    result = NetReturnScorer().score(
        {
            "crop_name": "Maize",
            "expected_yield_kg": 1000,
            "expected_price": 20,
            "input_costs": 5000,
            "subsidies": 500,
            "fertilizer_reductions": 250,
        },
        SuggestionContext(plot_id=1, season="Kharif"),
    )

    assert result.metrics["expected_net_return"] == 15750
    assert result.score > 50


def test_soil_scorer_rewards_nitrogen_and_organic_additions():
    scorer = SoilHealthScorer()
    positive = scorer.score(
        {"nitrogen_residual": 5, "organic_addition": 4},
        SuggestionContext(plot_id=1, season="Rabi"),
    )
    neutral = scorer.score({}, SuggestionContext(plot_id=1, season="Rabi"))

    assert positive.score > neutral.score
    assert "nitrogen" in positive.reason


def test_pest_scorer_penalizes_host_family_carryover():
    scorer = PestRiskScorer()
    result = scorer.score(
        {"crop_name": "Tomato", "crop_family": "Solanaceae", "host_crop_families": ["Solanaceae"], "baseline_pest_risk": 10},
        SuggestionContext(
            plot_id=1,
            season="Kharif",
            plot_history=[{"crop_name": "Potato", "crop_family": "Solanaceae"}],
        ),
    )

    assert result.score < 100
    assert result.metrics["pest_risk"] > 0
    assert "carryover" in result.reason


def test_pest_scorer_traces_matching_reviewed_regional_host_rule():
    result = PestRiskScorer().score(
        {"crop_name": "Chickpea", "baseline_pest_risk": 10,
         "pest_host_rule_records": [{"id": 44, "pest_name": "Pod borer", "host_crops": ["Maize"],
                                     "host_families": [], "risk_points": 30}]},
        SuggestionContext(plot_id=1, season="Kharif", plot_history=[{"crop_name": "Maize"}]),
    )
    assert result.metrics["pest_risk"] == 40
    assert result.metrics["matching_pest_record_ids"] == [44]
    assert "Pod borer" in result.reason
