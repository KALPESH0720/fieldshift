
from __future__ import annotations

from unittest.mock import patch

import pytest

from fieldshift.optimizer.constraints import (
    CropCandidate,
    OptimizationConstraints,
)
from pipelines.p5_optimizer.pipeline import (
    OptimizerPipelineError,
    build_crop_candidates,
    optimize_crop_candidates,
    run_p5_optimizer_pipeline,
)


@pytest.fixture
def candidate_data():
    return [
        {
            "crop": "Groundnut",
            "score": 0.9,
            "water_requirement_mm": 450,
            "soil_suitability": 0.85,
            "season": "Kharif",
            "family": "Legume",
            "root_depth": "medium",
            "expected_return": 50000,
            "nitrogen_benefit": 0.7,
        },
        {
            "crop": "Millet",
            "score": 0.8,
            "water_requirement_mm": 300,
            "soil_suitability": 0.9,
            "season": "Kharif",
            "family": "Cereal",
            "root_depth": "deep",
            "expected_return": 35000,
            "nitrogen_benefit": 0.2,
        },
    ]


@pytest.fixture
def constraints():
    return OptimizationConstraints(
        available_water_mm=1000,
        minimum_soil_suitability=0.3,
        maximum_crops=2,
        minimum_crop_diversity=1,
        avoid_same_family_consecutive=True,
    )


# --------------------------------------------------
# BUILD CROP CANDIDATES
# --------------------------------------------------

def test_build_crop_candidates_converts_data(candidate_data):
    candidates = build_crop_candidates(candidate_data)

    assert len(candidates) == 2
    assert all(isinstance(c, CropCandidate) for c in candidates)

    assert candidates[0].crop == "Groundnut"
    assert candidates[0].score == 0.9
    assert candidates[0].water_requirement_mm == 450
    assert candidates[0].soil_suitability == 0.85
    assert candidates[0].season == "Kharif"
    assert candidates[0].family == "Legume"
    assert candidates[0].root_depth == "medium"
    assert candidates[0].expected_return == 50000
    assert candidates[0].nitrogen_benefit == 0.7


def test_build_crop_candidates_applies_defaults():
    candidates = build_crop_candidates(
        [{"crop": "Rice", "score": 0.75}]
    )

    candidate = candidates[0]

    assert candidate.crop == "Rice"
    assert candidate.water_requirement_mm == 0
    assert candidate.soil_suitability == 1
    assert candidate.season == ""
    assert candidate.family == ""
    assert candidate.root_depth == "medium"
    assert candidate.expected_return == 0
    assert candidate.nitrogen_benefit == 0


def test_build_crop_candidates_rejects_empty_data():
    with pytest.raises(
        OptimizerPipelineError,
        match="Candidate data cannot be empty",
    ):
        build_crop_candidates([])


@pytest.mark.parametrize(
    "invalid_candidate",
    [
        {"score": 0.8},
        {"crop": "Rice"},
        {"crop": "Rice", "score": "bad"},
        None,
    ],
)
def test_build_crop_candidates_rejects_invalid_data(
    invalid_candidate,
):
    with pytest.raises(OptimizerPipelineError):
        build_crop_candidates([invalid_candidate])


def test_build_crop_candidates_converts_numeric_strings():
    candidates = build_crop_candidates(
        [
            {
                "crop": "Rice",
                "score": "0.8",
                "water_requirement_mm": "400",
            }
        ]
    )

    assert candidates[0].score == 0.8
    assert candidates[0].water_requirement_mm == 400


# --------------------------------------------------
# OPTIMIZE CROP CANDIDATES
# --------------------------------------------------

def test_optimize_crop_candidates_calls_solver(
    candidate_data, constraints
):
    expected_result = {
        "status": "success",
        "selected_crops": ["Groundnut"],
        "total_score": 0.9,
    }

    with patch(
        "pipelines.p5_optimizer.pipeline.solve_crop_optimization"
    ) as mock_solver:
        mock_solver.return_value = expected_result

        result = optimize_crop_candidates(
            candidate_data,
            constraints,
            objective="score",
        )

    mock_solver.assert_called_once()

    args, kwargs = mock_solver.call_args

    assert len(args[0]) == 2
    assert all(isinstance(c, CropCandidate) for c in args[0])
    assert args[1] is constraints
    assert kwargs == {
        "objective": "score",
        "use_fallback": True,
    }
    assert result == expected_result


def test_optimize_crop_candidates_passes_custom_objective(
    candidate_data, constraints
):
    with patch(
        "pipelines.p5_optimizer.pipeline.solve_crop_optimization"
    ) as mock_solver:
        mock_solver.return_value = {"status": "success"}

        optimize_crop_candidates(
            candidate_data,
            constraints,
            objective="return",
        )

    assert mock_solver.call_args.kwargs["objective"] == "return"


def test_optimize_crop_candidates_rejects_empty_candidates(
    constraints,
):
    with pytest.raises(OptimizerPipelineError):
        optimize_crop_candidates([], constraints)


# --------------------------------------------------
# P5 PIPELINE
# --------------------------------------------------

def test_p5_pipeline_returns_stage_and_solver_result(
    candidate_data, constraints
):
    expected_result = {
        "status": "success",
        "selected_crops": ["Groundnut"],
        "total_score": 0.9,
    }

    with patch(
        "pipelines.p5_optimizer.pipeline.solve_crop_optimization"
    ) as mock_solver:
        mock_solver.return_value = expected_result

        result = run_p5_optimizer_pipeline(
            candidate_data,
            constraints,
        )

    assert result == {
        "stage": "p5_optimizer",
        "status": "success",
        "optimization": expected_result,
    }


def test_p5_pipeline_propagates_solver_status(
    candidate_data, constraints
):
    solver_result = {
        "status": "infeasible",
        "selected_crops": [],
        "total_score": 0,
    }

    with patch(
        "pipelines.p5_optimizer.pipeline.solve_crop_optimization"
    ) as mock_solver:
        mock_solver.return_value = solver_result

        result = run_p5_optimizer_pipeline(
            candidate_data,
            constraints,
        )

    assert result["status"] == "infeasible"
    assert result["optimization"] == solver_result


def test_p5_pipeline_propagates_solver_exception(
    candidate_data, constraints
):
    with patch(
        "pipelines.p5_optimizer.pipeline.solve_crop_optimization",
        side_effect=RuntimeError("Solver failure"),
    ):
        with pytest.raises(RuntimeError, match="Solver failure"):
            run_p5_optimizer_pipeline(
                candidate_data,
                constraints,
            )
