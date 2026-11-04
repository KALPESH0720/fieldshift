
from unittest.mock import Mock

import pytest

from pipelines.p2_simulation.pipeline import (
    SimulationPipelineError,
    run_crop_simulation,
    run_p2_simulation_pipeline,
    validate_simulation_input,
)


@pytest.fixture
def grid():
    return {
        "grid_id": "GOA-001",
        "latitude": 15.49,
        "longitude": 73.82,
        "weather": {
            "rainfall_mm": 2200,
            "temperature_mean_c": 27.5,
        },
        "soil": {"ph": 6.2},
    }


@pytest.fixture
def simulator():
    return Mock(
        return_value={
            "yield_tonnes_per_ha": 4.2,
            "water_requirement_mm": 500,
        }
    )


def test_validate_simulation_input_accepts_valid_data(grid):
    validate_simulation_input(grid, "rice")


@pytest.mark.parametrize("crop", ["", " ", "   "])
def test_validate_simulation_input_rejects_empty_crop(
    grid, crop
):
    with pytest.raises(
        SimulationPipelineError,
        match="A crop name is required",
    ):
        validate_simulation_input(grid, crop)


def test_validate_simulation_input_requires_weather():
    with pytest.raises(
        SimulationPipelineError,
        match="Grid input must contain weather data",
    ):
        validate_simulation_input(
            {"grid_id": "GOA-001"},
            "rice",
        )


def test_run_crop_simulation_calls_simulator_correctly(
    grid, simulator
):
    config = {"model": "custom", "season": "kharif"}

    result = run_crop_simulation(
        grid,
        "rice",
        simulator,
        config,
    )

    simulator.assert_called_once_with(
        grid=grid,
        crop="rice",
        config=config,
    )

    assert result["crop"] == "rice"
    assert result["simulation_model"] == "custom"
    assert result["simulation_result"] == simulator.return_value


def test_run_crop_simulation_uses_default_model(
    grid, simulator
):
    result = run_crop_simulation(
        grid,
        "groundnut",
        simulator,
    )

    assert result["simulation_model"] == "custom"
    simulator.assert_called_once_with(
        grid=grid,
        crop="groundnut",
        config={},
    )


def test_run_crop_simulation_preserves_simulation_result(
    grid, simulator
):
    result = run_crop_simulation(
        grid,
        "rice",
        simulator,
    )

    assert result["simulation_result"] == {
        "yield_tonnes_per_ha": 4.2,
        "water_requirement_mm": 500,
    }


def test_run_crop_simulation_rejects_non_callable_simulator(
    grid,
):
    with pytest.raises(
        SimulationPipelineError,
        match="A valid simulator function is required",
    ):
        run_crop_simulation(
            grid,
            "rice",
            None,
        )


def test_run_crop_simulation_wraps_simulator_exception(
    grid,
):
    def failing_simulator(**kwargs):
        raise ValueError("Model computation failed")

    with pytest.raises(
        SimulationPipelineError,
        match="Simulation failed for rice",
    ) as exc_info:
        run_crop_simulation(
            grid,
            "rice",
            failing_simulator,
        )

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_run_crop_simulation_rejects_none_result(grid):
    simulator = Mock(return_value=None)

    with pytest.raises(
        SimulationPipelineError,
        match="Simulator returned no result",
    ):
        run_crop_simulation(
            grid,
            "rice",
            simulator,
        )


def test_p2_pipeline_simulates_multiple_crops(
    grid, simulator
):
    crops = ["rice", "groundnut", "millet"]

    result = run_p2_simulation_pipeline(
        grid,
        crops,
        simulator,
        {"model": "aquacrop"},
    )

    assert result["stage"] == "p2_simulation"
    assert result["status"] == "success"
    assert result["simulation_count"] == 3
    assert len(result["results"]) == 3

    assert [
        item["crop"] for item in result["results"]
    ] == crops

    assert all(
        item["simulation_model"] == "aquacrop"
        for item in result["results"]
    )

    assert simulator.call_count == 3


def test_p2_pipeline_rejects_empty_crop_list(
    grid, simulator
):
    with pytest.raises(
        SimulationPipelineError,
        match="At least one crop is required",
    ):
        run_p2_simulation_pipeline(
            grid,
            [],
            simulator,
        )


def test_p2_pipeline_stops_when_crop_simulation_fails(
    grid,
):
    simulator = Mock(
        side_effect=[
            {"yield": 4.2},
            RuntimeError("Simulation crashed"),
        ]
    )

    with pytest.raises(
        SimulationPipelineError,
        match="Simulation failed for groundnut",
    ):
        run_p2_simulation_pipeline(
            grid,
            ["rice", "groundnut", "millet"],
            simulator,
        )

    assert simulator.call_count == 2
