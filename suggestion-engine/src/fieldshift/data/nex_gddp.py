"""NASA NEX-GDDP-CMIP6 climate projection processing."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any


class NEXGDDPError(Exception):
    """Climate projection processing error."""


SUPPORTED_SCENARIOS = {
    "ssp126",
    "ssp245",
    "ssp370",
    "ssp585",
}


def validate_scenario(scenario: str) -> str:
    """Validate a CMIP6 scenario."""

    scenario = scenario.strip().lower()

    if scenario not in SUPPORTED_SCENARIOS:
        raise ValueError(
            f"Unsupported scenario: {scenario}"
        )

    return scenario


def load_climate_json(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Load prepared climate projection JSON."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        data = data.get("records", [])

    if not isinstance(data, list):
        raise NEXGDDPError(
            "Climate data must contain a list of records."
        )

    return data


def load_climate_csv(
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Load prepared climate projection CSV."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def normalize_climate_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate climate observations."""

    normalized = []

    for record in records:
        try:
            scenario = validate_scenario(
                str(record["scenario"])
            )

            temperature = float(record["temperature_c"])
            rainfall = float(record["rainfall_mm"])

            if not (
                math.isfinite(temperature)
                and math.isfinite(rainfall)
            ):
                raise ValueError("Climate values must be finite.")

            if rainfall < 0:
                raise ValueError("Rainfall cannot be negative.")

            normalized.append({
                "date": str(record["date"]),
                "scenario": scenario,
                "temperature_c": temperature,
                "rainfall_mm": rainfall,
            })

        except (KeyError, TypeError, ValueError) as exc:
            raise NEXGDDPError(
                f"Invalid climate record: {record}"
            ) from exc

    return normalized


def calculate_future_delta(
    historical_temperature: float,
    future_temperature: float,
    historical_rainfall: float,
    future_rainfall: float,
) -> dict[str, float | None]:
    """Calculate climate changes against historical baseline."""

    values = (
        historical_temperature,
        future_temperature,
        historical_rainfall,
        future_rainfall,
    )

    if not all(math.isfinite(float(v)) for v in values):
        raise ValueError("Climate values must be finite.")

    if historical_rainfall < 0 or future_rainfall < 0:
        raise ValueError("Rainfall cannot be negative.")

    temperature_delta = (
        future_temperature - historical_temperature
    )

    rainfall_change = (
        (
            future_rainfall - historical_rainfall
        ) / historical_rainfall * 100
        if historical_rainfall > 0
        else None
    )

    return {
        "temp_delta_c": temperature_delta,
        "rain_change_pct": rainfall_change,
    }


def summarize_future_climate(
    records: list[dict[str, Any]],
    historical_temperature: float,
    historical_rainfall: float,
) -> dict[str, Any]:
    """Summarize future climate for one scenario."""

    valid = normalize_climate_records(records)

    if not valid:
        raise ValueError("No climate records available.")

    scenarios = {item["scenario"] for item in valid}

    if len(scenarios) != 1:
        raise ValueError(
            "Summarize one climate scenario at a time."
        )

    future_temperature = mean(
        item["temperature_c"] for item in valid
    )

    future_rainfall = sum(
        item["rainfall_mm"] for item in valid
    )

    delta = calculate_future_delta(
        historical_temperature,
        future_temperature,
        historical_rainfall,
        future_rainfall,
    )

    return {
        "scenario": next(iter(scenarios)),
        "record_count": len(valid),
        "future_temperature_mean_c": future_temperature,
        "future_rainfall_total_mm": future_rainfall,
        **delta,
    }