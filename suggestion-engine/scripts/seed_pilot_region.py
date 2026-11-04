
"""Create a sample pilot-region JSON dataset.

Usage:
    py scripts/seed_pilot_region.py
    py scripts/seed_pilot_region.py --output tests/fixtures/pilot_region.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_pilot_region() -> dict:
    return {
        "location": {
            "region": "Goa",
            "latitude": 15.4909,
            "longitude": 73.8278,
        },
        "weather": {
            "rainfall_mm": 2200,
            "temperature_mean_c": 27.5,
            "temperature_max_c": 33.0,
            "temperature_min_c": 22.0,
        },
        "soil": {
            "ph": 6.2,
            "organic_carbon": 1.1,
            "clay": 35.0,
            "sand": 40.0,
            "silt": 25.0,
            "texture": "loam",
        },
        "satellite": {
            "ndvi": 0.62,
            "source": "sample",
        },
        "crop_history": [
            {"season": "Kharif-2024", "crop": "rice"},
            {"season": "Rabi-2024", "crop": "groundnut"},
        ],
        "metadata": {
            "dataset": "FieldShift pilot sample",
            "synthetic": True,
            "note": "Demo data only; not real-time NASA observations.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="tests/fixtures/pilot_region.json",
        help="Output JSON file",
    )
    args = parser.parse_args()

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_pilot_region(), indent=2),
        encoding="utf-8",
    )

    print(f"Pilot sample created: {path.resolve()}")


if __name__ == "__main__":
    main()
