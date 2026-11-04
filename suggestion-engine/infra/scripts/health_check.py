
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_pipeline_output() -> bool:
    output_path = os.getenv(
        "FIELDSHIFT_OUTPUT_PATH",
        "outputs/fieldshift_result.json",
    )

    path = PROJECT_ROOT / output_path

    if not path.exists():
        print(f"UNHEALTHY: Pipeline output missing: {path}")
        return False

    try:
        with path.open("r", encoding="utf-8") as file:
            result = json.load(file)

    except (OSError, json.JSONDecodeError) as exc:
        print(f"UNHEALTHY: Invalid pipeline output: {exc}")
        return False

    if result.get("status") != "success":
        print("UNHEALTHY: Pipeline did not report success")
        return False

    print("HEALTHY: FieldShift pipeline output verified")
    return True


def main() -> int:
    return 0 if check_pipeline_output() else 1


if __name__ == "__main__":
    sys.exit(main())
