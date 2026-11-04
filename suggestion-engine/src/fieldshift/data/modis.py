"""MODIS vegetation observation processing."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


class MODISError(Exception):
    """MODIS data processing error."""


def calculate_ndvi(
    nir: float,
    red: float,
) -> float | None:
    """Calculate NDVI from near-infrared and red reflectance."""

    if not math.isfinite(nir) or not math.isfinite(red):
        raise ValueError("Reflectance values must be finite.")

    denominator = nir + red

    if denominator == 0:
        return None

    value = (nir - red) / denominator

    if not -1 <= value <= 1:
        return None

    return value


def load_modis_json(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Load prepared MODIS observations from JSON."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        data = data.get("observations", [])

    if not isinstance(data, list):
        raise MODISError("Expected a list of observations.")

    return data


def load_modis_csv(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Load prepared MODIS observations from CSV."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def normalize_observations(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Validate observations.

    Accepted fields:
    date, ndvi

    Or:
    date, nir, red
    """

    output = []

    for item in observations:
        try:
            day = str(item["date"])

            if item.get("ndvi") not in (None, ""):
                ndvi = float(item["ndvi"])
            else:
                ndvi = calculate_ndvi(
                    float(item["nir"]),
                    float(item["red"]),
                )

            if ndvi is None:
                continue

            if not -1 <= ndvi <= 1:
                continue

            output.append({
                "date": day,
                "ndvi": ndvi,
            })

        except (KeyError, TypeError, ValueError) as exc:
            raise MODISError(
                f"Invalid MODIS observation: {item}"
            ) from exc

    output.sort(key=lambda item: item["date"])

    return output


def summarize_ndvi(
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate vegetation statistics."""

    valid = normalize_observations(observations)

    if not valid:
        return {
            "count": 0,
            "ndvi_mean": None,
            "ndvi_min": None,
            "ndvi_max": None,
            "ndvi_cv": None,
            "latest_ndvi": None,
        }

    values = [item["ndvi"] for item in valid]

    average = mean(values)

    variance = (
        sum((value - average) ** 2 for value in values)
        / len(values)
    )

    standard_deviation = math.sqrt(variance)

    return {
        "count": len(values),
        "ndvi_mean": average,
        "ndvi_min": min(values),
        "ndvi_max": max(values),
        "ndvi_cv": (
            standard_deviation / abs(average)
            if average != 0 else None
        ),
        "latest_ndvi": values[-1],
        "latest_date": valid[-1]["date"],
    }