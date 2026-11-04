
from __future__ import annotations

from unittest.mock import patch

import pytest

from fieldshift.learning.weight_tuning import (
    DEFAULT_WEIGHTS,
    WeightTuningError,
)
from pipelines.p4_learning.pipeline import (
    LearningPipelineError,
    run_prior_learning,
    run_weight_learning,
    run_p4_learning_pipeline,
)


@pytest.fixture
def baseline_scores():
    return {
        "Groundnut": 0.85,
        "Millet": 0.75,
        "Rice": 0.65,
    }


@pytest.fixture
def feedback():
    return {
        "Groundnut": [0.9, 0.8],
        "Millet": [0.7, 0.8],
    }


@pytest.fixture
def historical_scores():
    return [
        {
            "soil_benefit": 0.80,
            "economic_return": 0.70,
            "water_fit": 0.90,
            "climate_resilience": 0.60,
            "rotation_benefit": 0.75,
        },
        {
            "soil_benefit": 0.60,
            "economic_return": 0.90,
            "water_fit": 0.70,
            "climate_resilience": 0.80,
            "rotation_benefit": 0.65,
        },
        {
            "soil_benefit": 0.90,
            "economic_return": 0.60,
            "water_fit": 0.80,
            "climate_resilience": 0.70,
            "rotation_benefit": 0.85,
        },
        {
            "soil_benefit": 0.70,
            "economic_return": 0.80,
            "water_fit": 0.60,
            "climate_resilience": 0.90,
            "rotation_benefit": 0.55,
        },
        {
            "soil_benefit": 0.85,
            "economic_return": 0.75,
            "water_fit": 0.85,
            "climate_resilience": 0.65,
            "rotation_benefit": 0.90,
        },
    ]


@pytest.fixture
def outcomes():
    return [0.65, 0.75, 0.80, 0.70, 0.90]


# --------------------------------------------------
# PRIOR LEARNING
# --------------------------------------------------

def test_run_prior_learning_builds_and_ranks_priors(
    baseline_scores, feedback
):
    result = run_prior_learning(baseline_scores, feedback)

    assert "priors" in result
    assert "ranked_priors" in result
    assert result["priors"]
    assert result["ranked_priors"]


def test_run_prior_learning_uses_confidence(
    baseline_scores, feedback
):
    with patch(
        "pipelines.p4_learning.pipeline.build_priors"
    ) as mock_build:
        mock_build.return_value = {
            "Groundnut": {"score": 0.85}
        }

        with patch(
            "pipelines.p4_learning.pipeline.update_priors_from_feedback"
        ) as mock_update:
            mock_update.return_value = {
                "Groundnut": {"score": 0.9}
            }

            with patch(
                "pipelines.p4_learning.pipeline.rank_crop_priors"
            ) as mock_rank:
                mock_rank.return_value = ["Groundnut"]

                result = run_prior_learning(
                    baseline_scores,
                    feedback,
                    confidence=0.8,
                )

    mock_build.assert_called_once_with(
        baseline_scores,
        confidence=0.8,
    )

    assert result["ranked_priors"] == ["Groundnut"]


def test_run_prior_learning_rejects_empty_baseline():
    with pytest.raises(
        LearningPipelineError,
        match="Baseline crop scores are required",
    ):
        run_prior_learning({}, {})


def test_run_prior_learning_passes_feedback(
    baseline_scores, feedback
):
    with patch(
        "pipelines.p4_learning.pipeline.update_priors_from_feedback"
    ) as mock_update:
        mock_update.return_value = {
            "Groundnut": {"score": 0.9}
        }

        with patch(
            "pipelines.p4_learning.pipeline.build_priors"
        ) as mock_build:
            mock_build.return_value = {
                "Groundnut": {"score": 0.85}
            }

            with patch(
                "pipelines.p4_learning.pipeline.rank_crop_priors"
            ) as mock_rank:
                mock_rank.return_value = ["Groundnut"]

                run_prior_learning(
                    baseline_scores,
                    feedback,
                )

    mock_update.assert_called_once_with(
        mock_build.return_value,
        feedback,
    )


# --------------------------------------------------
# WEIGHT LEARNING
# --------------------------------------------------

def test_run_weight_learning_returns_weights_and_comparison(
    historical_scores, outcomes
):
    result = run_weight_learning(
        historical_scores,
        outcomes,
    )

    assert set(result) == {
        "old_weights",
        "new_weights",
        "comparison",
    }

    assert result["old_weights"] == DEFAULT_WEIGHTS
    assert result["new_weights"]
    assert result["comparison"]["changes"]
    assert result["comparison"]["total_absolute_change"] >= 0


def test_run_weight_learning_uses_custom_current_weights(
    historical_scores, outcomes
):
    current_weights = {
        "soil_benefit": 0.20,
        "economic_return": 0.30,
        "water_fit": 0.20,
        "climate_resilience": 0.20,
        "rotation_benefit": 0.10,
    }

    result = run_weight_learning(
        historical_scores,
        outcomes,
        current_weights=current_weights,
    )

    assert result["old_weights"] == current_weights


def test_run_weight_learning_uses_default_weights(
    historical_scores, outcomes
):
    with patch(
        "pipelines.p4_learning.pipeline.get_default_weights"
    ) as mock_defaults:
        mock_defaults.return_value = dict(DEFAULT_WEIGHTS)

        with patch(
            "pipelines.p4_learning.pipeline.tune_from_outcomes"
        ) as mock_tune:
            mock_tune.return_value = dict(DEFAULT_WEIGHTS)

            with patch(
                "pipelines.p4_learning.pipeline.compare_weight_versions"
            ) as mock_compare:
                mock_compare.return_value = {
                    "changes": {},
                    "total_absolute_change": 0,
                }

                result = run_weight_learning(
                    historical_scores,
                    outcomes,
                )

    mock_defaults.assert_called_once()
    assert result["old_weights"] == DEFAULT_WEIGHTS


def test_run_weight_learning_passes_learning_rate(
    historical_scores, outcomes
):
    current_weights = dict(DEFAULT_WEIGHTS)

    with patch(
        "pipelines.p4_learning.pipeline.tune_from_outcomes"
    ) as mock_tune:
        mock_tune.return_value = dict(DEFAULT_WEIGHTS)

        with patch(
            "pipelines.p4_learning.pipeline.compare_weight_versions"
        ) as mock_compare:
            mock_compare.return_value = {}

            run_weight_learning(
                historical_scores,
                outcomes,
                current_weights,
                learning_rate=0.1,
            )

    mock_tune.assert_called_once_with(
        current_weights,
        historical_scores,
        outcomes,
        0.1,
    )


def test_run_weight_learning_rejects_less_than_five_observations(
    historical_scores
):
    with pytest.raises(
        WeightTuningError,
        match="At least five outcome observations",
    ):
        run_weight_learning(
            historical_scores[:2],
            [0.8, 0.7],
        )


# --------------------------------------------------
# P4 PIPELINE
# --------------------------------------------------

def test_p4_pipeline_without_historical_data(
    baseline_scores, feedback
):
    result = run_p4_learning_pipeline(
        baseline_scores,
        feedback,
    )

    assert result["stage"] == "p4_learning"
    assert result["status"] == "success"
    assert result["priors"]["priors"]
    assert result["weights"] is None


def test_p4_pipeline_with_historical_data(
    baseline_scores,
    feedback,
    historical_scores,
    outcomes,
):
    result = run_p4_learning_pipeline(
        baseline_scores,
        feedback,
        historical_scores,
        outcomes,
    )

    assert result["stage"] == "p4_learning"
    assert result["status"] == "success"
    assert result["weights"] is not None
    assert result["weights"]["old_weights"]
    assert result["weights"]["new_weights"]
    assert result["weights"]["comparison"] is not None


def test_p4_pipeline_skips_weight_learning_without_outcomes(
    baseline_scores,
    feedback,
    historical_scores,
):
    result = run_p4_learning_pipeline(
        baseline_scores,
        feedback,
        historical_scores,
        outcomes=None,
    )

    assert result["weights"] is None


def test_p4_pipeline_skips_weight_learning_without_scores(
    baseline_scores,
    feedback,
    outcomes,
):
    result = run_p4_learning_pipeline(
        baseline_scores,
        feedback,
        historical_scores=None,
        outcomes=outcomes,
    )

    assert result["weights"] is None


def test_p4_pipeline_propagates_learning_error():
    with pytest.raises(LearningPipelineError):
        run_p4_learning_pipeline({}, {})
