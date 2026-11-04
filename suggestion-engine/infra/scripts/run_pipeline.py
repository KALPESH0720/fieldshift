
import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.compile import run_fieldshift_pipeline


logger = logging.getLogger("fieldshift.infrastructure.runner")


def load_config() -> dict[str, Any]:
    config_path = os.getenv(
        "FIELDSHIFT_CONFIG_PATH",
        "infra/config/app.yaml",
    )

    path = PROJECT_ROOT / config_path

    if not path.exists():
        raise FileNotFoundError(f"Missing configuration: {path}")

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("Invalid FieldShift configuration")

    return config


def load_json(path: str) -> Any:
    file_path = PROJECT_ROOT / path

    if not file_path.exists():
        raise FileNotFoundError(f"Missing input file: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_callable(import_path: str):
    if ":" not in import_path:
        raise ValueError(
            "Callable must use module:function format"
        )

    module_name, function_name = import_path.split(":", 1)

    module = importlib.import_module(module_name)
    function = getattr(module, function_name)

    if not callable(function):
        raise TypeError(f"{import_path} is not callable")

    return function


def configure_logging(config: dict[str, Any]) -> None:
    logging_config = config.get("logging", {})
    level = logging_config.get("level", "INFO")

    logging.basicConfig(
        level=getattr(logging, str(level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def execute_pipeline(config: dict[str, Any]) -> dict[str, Any]:
    execution = config.get("execution", {})

    required = [
        "grid_input",
        "crops",
        "simulator",
        "simulation_config",
        "monitor_checks",
        "monitor_inputs",
        "baseline_scores",
        "farmer_feedback",
        "candidate_data",
        "optimization_constraints",
    ]

    missing = [key for key in required if key not in execution]

    if missing:
        raise ValueError(
            "Missing pipeline execution configuration: "
            + ", ".join(missing)
        )

    simulator = load_callable(execution["simulator"])

    monitor_checks = {
        name: load_callable(path)
        for name, path in execution["monitor_checks"].items()
    }

    inputs = {
        "grid_input": execution["grid_input"],
        "crops": execution["crops"],
        "simulator": simulator,
        "simulation_config": execution["simulation_config"],
        "monitor_checks": monitor_checks,
        "monitor_inputs": execution["monitor_inputs"],
        "baseline_scores": execution["baseline_scores"],
        "farmer_feedback": execution["farmer_feedback"],
        "candidate_data": execution["candidate_data"],
        "optimization_constraints": execution[
            "optimization_constraints"
        ],
        "historical_scores": execution.get("historical_scores"),
        "historical_outcomes": execution.get("historical_outcomes"),
        "objective": execution.get("objective", "score"),
    }

    return run_fieldshift_pipeline(**inputs)


def main() -> int:
    try:
        config = load_config()
        configure_logging(config)

        logger.info("Starting FieldShift pipeline")

        result = execute_pipeline(config)

        output_path = os.getenv(
            "FIELDSHIFT_OUTPUT_PATH",
            "outputs/fieldshift_result.json",
        )

        destination = PROJECT_ROOT / output_path
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("w", encoding="utf-8") as file:
            json.dump(result, file, indent=2, default=str)

        logger.info("FieldShift pipeline completed")
        logger.info("Output saved to %s", destination)

        return 0

    except Exception:
        logger.exception("FieldShift pipeline execution failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
