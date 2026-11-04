"""NASA SMAP soil moisture data processing."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


class SMAPError(Exception):
    """SMAP processing error."""


def validate_moisture(value: float) -> float:
    """Validate volumetric soil moisture."""

    value = float(value)

    if not math.isfinite(value):
        raise ValueError("Moisture must be finite.")

    if not 0 <= value <= 1:
        raise ValueError(
            "Volumetric soil moisture must be between 0 and 1."
        )

    return value


def load_smap_json(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Load prepared SMAP observations from JSON."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        data = data.get("observations", [])

    if not isinstance(data, list):
        raise SMAPError("Expected a list of SMAP observations.")

    return data


def load_smap_csv(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Load prepared SMAP observations from CSV."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def normalize_smap(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate and normalize soil moisture observations."""

    output = []

    for item in observations:
        try:
            surface = validate_moisture(
                item["surface_moisture"]
            )

            root_zone = item.get("root_zone_moisture")

            if root_zone not in (None, ""):
                root_zone = validate_moisture(root_zone)
            else:
                root_zone = None

            output.append({
                "date": str(item["date"]),
                "surface_moisture": surface,
                "root_zone_moisture": root_zone,
            })

        except (KeyError, TypeError, ValueError) as exc:
            raise SMAPError(
                f"Invalid SMAP record: {item}"
            ) from exc

    output.sort(key=lambda item: item["date"])

    return output


def calculate_drought_frequency(
    observations: list[dict[str, Any]],
    threshold: float = 0.15,
) -> float | None:
    """Estimate fraction of observations below a moisture threshold."""

    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between 0 and 1.")

    records = normalize_smap(observations)

    if not records:
        return None

    dry_count = sum(
        item["surface_moisture"] < threshold
        for item in records
    )

    return dry_count / len(records)


def calculate_root_zone_water(
    observations: list[dict[str, Any]],
    soil_depth_mm: float,
    wilting_point: float,
    field_capacity: float,
) -> float | None:
    """
    Calculate available root-zone water in mm.

    Uses volumetric root-zone moisture:
    (moisture - wilting point) * soil depth.

    This requires a suitable root-zone moisture estimate.
    """

    if soil_depth_mm <= 0:
        raise ValueError("Soil depth must be positive.")

    if not (
        0 <= wilting_point < field_capacity <= 1
    ):
        raise ValueError("Invalid soil moisture limits.")

    records = normalize_smap(observations)

    root_values = [
        item["root_zone_moisture"]
        for item in records
        if item["root_zone_moisture"] is not None
    ]

    if not root_values:
        return None

    average = mean(root_values)

    available_fraction = max(
        0.0,
        min(field_capacity, average) - wilting_point,
    )

    return available_fraction * soil_depth_mm


def summarize_smap(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate a soil moisture summary."""

    records = normalize_smap(observations)

    if not records:
        return {
            "observation_count": 0,
            "surface_moisture_mean": None,
            "root_zone_moisture_mean": None,
            "drought_frequency": None,
        }

    surface = [
        item["surface_moisture"]
        for item in records
    ]

    root_zone = [
        item["root_zone_moisture"]
        for item in records
        if item["root_zone_moisture"] is not None
    ]

    return {
        "observation_count": len(records),
        "surface_moisture_mean": mean(surface),
        "root_zone_moisture_mean": (
            mean(root_zone) if root_zone else None
        ),
        "drought_frequency": calculate_drought_frequency(
            records
        ),
        "latest_date": records[-1]["date"],
    }