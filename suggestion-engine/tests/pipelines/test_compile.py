
from unittest.mock import Mock, call

import pytest

import pipelines.compile as pipeline_module


@pytest.fixture
def pipeline_mocks(monkeypatch):
    p1 = Mock(return_value={"grid": "grid-data"})
    p2 = Mock(return_value={"simulation": "simulation-data"})
    p3 = Mock(return_value={"monitoring": "monitoring-data"})
    p4 = Mock(return_value={"learning": "learning-data"})
    p5 = Mock(return_value={"optimization": "optimization-data"})

    monkeypatch.setattr(
        pipeline_module, "run_p1_grid_pipeline", p1
    )
    monkeypatch.setattr(
        pipeline_module, "run_p2_simulation_pipeline", p2
    )
    monkeypatch.setattr(
        pipeline_module, "run_p3_monitor_pipeline", p3
    )
    monkeypatch.setattr(
        pipeline_module, "run_p4_learning_pipeline", p4
    )
    monkeypatch.setattr(
        pipeline_module, "run_p5_optimizer_pipeline", p5
    )

    return p1, p2, p3, p4, p5


def test_master_pipeline_executes_all_stages(pipeline_mocks):
    p1, p2, p3, p4, p5 = pipeline_mocks

    grid_input = {"latitude": 15.49, "longitude": 73.82}
    crops = ["rice", "groundnut"]
    simulator = Mock()
    simulation_config = {"season": "kharif"}
    monitor_checks = {"rainfall": Mock()}
    monitor_inputs = {"rainfall": {"value": 200}}
    baseline_scores = {"rice": 0.7}
    farmer_feedback = {"rice": [0.8, 0.9]}
    candidate_data = [{"crop": "rice", "score": 0.8}]
    constraints = object()

    result = pipeline_module.run_fieldshift_pipeline(
        grid_input=grid_input,
        crops=crops,
        simulator=simulator,
        simulation_config=simulation_config,
        monitor_checks=monitor_checks,
        monitor_inputs=monitor_inputs,
        baseline_scores=baseline_scores,
        farmer_feedback=farmer_feedback,
        candidate_data=candidate_data,
        optimization_constraints=constraints,
        objective="score",
    )

    # Verify P1 input.
    p1.assert_called_once_with(grid_input)

    # Verify P2 receives the grid produced by P1.
    p2.assert_called_once_with(
        "grid-data",
        crops,
        simulator,
        simulation_config,
    )

    # Verify P3 receives monitor configuration.
    p3.assert_called_once_with(
        monitor_checks,
        monitor_inputs,
    )

    # Verify P4 receives historical learning inputs.
    p4.assert_called_once_with(
        baseline_scores,
        farmer_feedback,
        None,
        None,
    )

    # Verify P5 receives optimizer inputs.
    p5.assert_called_once_with(
        candidate_data,
        constraints,
        "score",
    )

    # Verify final master pipeline output.
    assert result == {
        "pipeline": "fieldshift",
        "status": "success",
        "grid": {"grid": "grid-data"},
        "simulation": {"simulation": "simulation-data"},
        "monitoring": {"monitoring": "monitoring-data"},
        "learning": {"learning": "learning-data"},
        "optimization": {"optimization": "optimization-data"},
    }


def test_master_pipeline_passes_historical_data(pipeline_mocks):
    _, _, _, p4, _ = pipeline_mocks

    historical_scores = [{"rice": 0.8}]
    historical_outcomes = [0.9]

    pipeline_module.run_fieldshift_pipeline(
        grid_input={},
        crops=[],
        simulator=Mock(),
        simulation_config={},
        monitor_checks={},
        monitor_inputs={},
        baseline_scores={},
        farmer_feedback={},
        candidate_data=[],
        optimization_constraints=object(),
        historical_scores=historical_scores,
        historical_outcomes=historical_outcomes,
    )

    p4.assert_called_once_with(
        {},
        {},
        historical_scores,
        historical_outcomes,
    )


@pytest.mark.parametrize(
    "failed_stage",
    [
        "run_p1_grid_pipeline",
        "run_p2_simulation_pipeline",
        "run_p3_monitor_pipeline",
        "run_p4_learning_pipeline",
        "run_p5_optimizer_pipeline",
    ],
)
def test_master_pipeline_wraps_stage_failures(
    monkeypatch,
    failed_stage,
):
    def fail(*args, **kwargs):
        raise ValueError("simulated stage failure")

    monkeypatch.setattr(
        pipeline_module,
        failed_stage,
        fail,
    )

    with pytest.raises(
        pipeline_module.FieldShiftPipelineError
    ) as exc_info:
        pipeline_module.run_fieldshift_pipeline(
            grid_input={},
            crops=[],
            simulator=Mock(),
            simulation_config={},
            monitor_checks={},
            monitor_inputs={},
            baseline_scores={},
            farmer_feedback={},
            candidate_data=[],
            optimization_constraints=object(),
        )

    assert "pipeline execution failed" in str(
        exc_info.value
    ).lower()

    assert isinstance(exc_info.value.__cause__, ValueError)
