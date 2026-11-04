
"""Run the FieldShift P1 grid-layer pipeline locally.

Usage:
    py scripts/run_p1_local.py --input tests/fixtures/pilot_region.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --------------------------------------------------
# Add project root to Python import path
# --------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# --------------------------------------------------
# Import P1 pipeline
# --------------------------------------------------
from pipelines.p1_grid_layers.pipeline import run_p1_grid_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run FieldShift P1 grid-layer pipeline"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to P1 JSON input file",
    )

    parser.add_argument(
        "--output",
        default="p1_output.json",
        help="Output JSON path",
    )

    args = parser.parse_args()

    # --------------------------------------------------
    # Load input JSON
    # --------------------------------------------------
    input_path = Path(args.input)

    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid input JSON: {exc}")

    # --------------------------------------------------
    # Run P1 pipeline
    # --------------------------------------------------
    try:
        result = run_p1_grid_pipeline(data)
    except Exception as exc:
        raise SystemExit(f"P1 pipeline failed: {exc}")

    # --------------------------------------------------
    # Convert result into JSON-compatible format
    # --------------------------------------------------
    if hasattr(result, "__dataclass_fields__"):
        result = result.__dict__

    # --------------------------------------------------
    # Save output
    # --------------------------------------------------
    output_path = Path(args.output)

    if not output_path.is_absolute():
        output_path = ROOT / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(result, indent=2, default=str),
        encoding="utf-8",
    )

    print("\nFieldShift P1 completed successfully.")
    print(f"Input : {input_path.resolve()}")
    print(f"Output: {output_path.resolve()}")


if __name__ == "__main__":
    main()
