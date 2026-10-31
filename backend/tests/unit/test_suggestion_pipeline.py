from unittest.mock import Mock

from app.suggestion_engine.pipeline import PipelineOrchestrator
from app.suggestion_engine.rules.base import RuleDecision
from app.suggestion_engine.scorers.base import ScoreResult
from app.suggestion_engine.rules.crop_repeat_gap_rule import CropRepeatGapRule
from app.suggestion_engine.pipeline import SuggestionContext


def test_pipeline_filters_scores_and_ranks_candidates():
    candidates = [
        {"crop_name": "Millet", "net_return": 100},
        {"crop_name": "Rice", "net_return": 200},
        {"crop_name": "Cotton", "net_return": 500},
    ]
    candidate_filter = Mock()
    candidate_filter.apply.return_value = candidates[:2]
    rule = Mock()
    rule.evaluate.return_value = RuleDecision(allowed=True, reason="Fits the crop rotation.")
    scorer = Mock()
    scorer.key = "net_return"
    scorer.weight = 1.0
    scorer.score.side_effect = lambda candidate, context: ScoreResult(
        score=80 if candidate["crop_name"] == "Rice" else 40,
        reason=f"Estimated return is {candidate['net_return']}.",
        metrics={"expected_net_return": candidate["net_return"]},
    )

    response = PipelineOrchestrator(
        filters=[candidate_filter], rules=[rule], scorers=[scorer]
    ).run(
        plot_id=7,
        season="Kharif",
        candidates=candidates,
        plot_history=[{"crop_name": "Wheat"}],
        soil_data={"ph": 6.5},
        market_prices=[{"crop_name": "Rice", "modal_price": 25}],
        preferred_crops=["Rice"],
    )

    assert [option.crop_name for option in response.options] == ["Rice", "Millet"]
    assert response.options[0].score == 80
    assert response.options[0].expected_net_return == 200
    assert "This crop matches your stated preference." in response.options[0].reasons
    assert "Fits the crop rotation." in response.options[0].reasons
    candidate_filter.apply.assert_called_once()


def test_pipeline_discards_rule_rejections_and_uses_weighted_scores():
    rule = Mock()
    rule.evaluate.side_effect = lambda candidate, context: RuleDecision(
        allowed=candidate["crop_name"] != "Rejected", reason="Rotation check passed."
    )
    high_return = Mock()
    high_return.key = "net_return"
    high_return.weight = 3
    high_return.score.side_effect = lambda candidate, context: 90 if candidate["crop_name"] == "A" else 20
    soil = Mock()
    soil.key = "soil_health"
    soil.weight = 1
    soil.score.return_value = 50

    response = PipelineOrchestrator(rules=[rule], scorers=[high_return, soil]).run(
        plot_id=1,
        season="Rabi",
        candidates=[{"crop_name": "A"}, {"crop_name": "B"}, {"crop_name": "Rejected"}],
    )

    assert [option.crop_name for option in response.options] == ["A", "B"]
    assert response.options[0].score == 80
    assert response.options[1].score == 27.5


def test_crop_repeat_gap_rule_requires_a_full_intervening_season():
    rule = CropRepeatGapRule(minimum_gap_seasons=1)
    context = SuggestionContext(
        plot_id=1, season="Kharif",
        plot_history=[{"crop_name": "Ragi", "season_distance": 1}],
    )
    assert rule.evaluate({"crop_name": "Ragi"}, context).allowed is False
    context = SuggestionContext(
        plot_id=1, season="Kharif",
        plot_history=[{"crop_name": "Ragi", "season_distance": 2}],
    )
    assert rule.evaluate({"crop_name": "Ragi"}, context).allowed is True
