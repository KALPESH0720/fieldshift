
from __future__ import annotations

import logging
from typing import Any, Callable, Mapping

logger = logging.getLogger("fieldshift.pipeline.simulation")


class SimulationPipelineError(RuntimeError):
    """Simulation pipeline failure."""

def validate_simulation_input(
    grid: Mapping[str, Any],
    crop: str,
) -> None:
    if not crop or not crop.strip():
        raise SimulationPipelineError(
            "A crop name is required."
        )

    if "weather" not in grid:
        raise SimulationPipelineError(
            "Grid input must contain weather data."
        )


def run_crop_simulation(
    grid: Mapping[str, Any],
    crop: str,
    simulator: Callable[..., Any],
    simulation_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:

    validate_simulation_input(grid, crop)

    if not callable(simulator):
        raise SimulationPipelineError(
            "A valid simulator function is required."
        )

    try:
        result = simulator(
            grid=grid,
            crop=crop,
            config=dict(simulation_config or {}),
        )
    except Exception as exc:
        logger.exception(
            "Simulation failed for crop %s", crop
        )
        raise SimulationPipelineError(
            f"Simulation failed for {crop}."
        ) from exc

    if result is None:
        raise SimulationPipelineError(
            "Simulator returned no result."
        )

    return {
        "crop": crop,
        "simulation_result": result,
        "simulation_model": (
            simulation_config or {}
        ).get("model", "custom"),
    }


def run_p2_simulation_pipeline(
    grid: Mapping[str, Any],
    crops: list[str],
    simulator: Callable[..., Any],
    simulation_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute simulation for multiple candidate crops."""

    if not crops:
        raise SimulationPipelineError(
            "At least one crop is required."
        )

    results = []

    for crop in crops:
        results.append(
            run_crop_simulation(
                grid,
                crop,
                simulator,
                simulation_config,
            )
        )

    return {
        "stage": "p2_simulation",
        "status": "success",
        "simulation_count": len(results),
        "results": results,
    }
