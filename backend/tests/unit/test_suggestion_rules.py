from app.suggestion_engine.pipeline import SuggestionContext
from app.suggestion_engine.rules import CropFamilyRule, LegumeRotationRule, RootDepthRule


def test_tomato_after_potato_has_explicit_same_family_rejection():
    context = SuggestionContext(
        plot_id=1,
        season="Kharif",
        plot_history=[{"crop_name": "Potato", "crop_family": "Solanaceae"}],
    )

    decision = CropFamilyRule().evaluate(
        {"crop_name": "Tomato", "crop_family": "solanaceae"}, context
    )

    assert decision.allowed is False
    assert "Tomato" in decision.reason
    assert "Potato" in decision.reason
    assert "rotate" in decision.reason


def test_legume_is_prioritized_after_cereal_and_root_depth_alternates():
    context = SuggestionContext(
        plot_id=1,
        season="Rabi",
        plot_history=[{"crop_name": "Wheat", "crop_family": "Poaceae", "root_depth": "deep"}],
    )

    legume = LegumeRotationRule().evaluate(
        {"crop_name": "Chickpea", "crop_family": "Fabaceae", "root_depth": "shallow"}, context
    )
    same_depth = RootDepthRule().evaluate(
        {"crop_name": "Barley", "crop_family": "Poaceae", "root_depth": "deep"}, context
    )
    alternate_depth = RootDepthRule().evaluate(
        {"crop_name": "Chickpea", "crop_family": "Fabaceae", "root_depth": "shallow"}, context
    )

    assert legume.allowed is True
    assert legume.priority_adjustment > 0
    assert "nitrogen" in legume.reason
    assert same_depth.allowed is False
    assert alternate_depth.allowed is True
