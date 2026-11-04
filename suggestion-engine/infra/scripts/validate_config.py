
from pathlib import Path
import sys

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

APP_CONFIG = PROJECT_ROOT / "infra/config/app.yaml"
LOGGING_CONFIG = PROJECT_ROOT / "infra/config/logging.yaml"

EXPECTED_STAGES = [
    "p1_grid_layers",
    "p2_simulation",
    "p3_monitor",
    "p4_learning",
    "p5_optimizer",
]


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing configuration: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML mapping: {path}")

    return data


def validate_app_config() -> None:
    config = load_yaml(APP_CONFIG)

    app = config.get("app")
    pipeline = config.get("pipeline")
    logging_config = config.get("logging")
    monitoring = config.get("monitoring")

    if not isinstance(app, dict):
        raise ValueError("'app' must be a mapping")

    if app.get("name") != "FieldShift":
        raise ValueError("Application name must be FieldShift")

    if not isinstance(pipeline, dict):
        raise ValueError("'pipeline' must be a mapping")

    if pipeline.get("stages") != EXPECTED_STAGES:
        raise ValueError("Pipeline stages do not match P1-P5")

    if not isinstance(logging_config, dict):
        raise ValueError("'logging' must be a mapping")

    if not isinstance(monitoring, dict):
        raise ValueError("'monitoring' must be a mapping")

    print("VALID: app.yaml")


def validate_logging_config() -> None:
    config = load_yaml(LOGGING_CONFIG)

    if config.get("version") != 1:
        raise ValueError("Logging version must be 1")

    if not isinstance(config.get("handlers"), dict):
        raise ValueError("'handlers' must be a mapping")

    if not isinstance(config.get("formatters"), dict):
        raise ValueError("'formatters' must be a mapping")

    print("VALID: logging.yaml")


def main() -> int:
    try:
        validate_app_config()
        validate_logging_config()
        print("\nAll infrastructure configurations are valid.")
        return 0

    except Exception as exc:
        print(f"\nConfiguration validation failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
