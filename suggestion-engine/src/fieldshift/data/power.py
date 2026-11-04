"""NASA POWER weather data integration."""

from __future__ import annotations

import json
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any


BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)


class PowerAPIError(Exception):
    """NASA POWER request or response error."""


def fetch_power_data(
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
    parameters: tuple[str, ...] = (
        "PRECTOTCORR",
        "T2M",
        "T2M_MAX",
        "T2M_MIN",
    ),
    timeout: int = 30,
) -> dict[str, Any]:
    """Fetch daily weather data from NASA POWER."""

    if not -90 <= latitude <= 90:
        raise ValueError("Invalid latitude.")

    if not -180 <= longitude <= 180:
        raise ValueError("Invalid longitude.")

    if end_date < start_date:
        raise ValueError("End date cannot precede start date.")

    if not parameters:
        raise ValueError("At least one parameter is required.")

    query = {
        "parameters": ",".join(parameters),
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
    }

    url = f"{BASE_URL}?{urlencode(query)}"

    request = Request(
        url,
        headers={"User-Agent": "FieldShift/0.1"},
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

    except Exception as exc:
        raise PowerAPIError(
            f"Unable to fetch NASA POWER data: {exc}"
        ) from exc

    if "properties" not in result:
        raise PowerAPIError(
            "NASA POWER response is missing properties."
        )

    return result


def extract_daily_values(
    response: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert NASA POWER JSON into daily records."""

    try:
        parameters = response["properties"]["parameter"]
    except (KeyError, TypeError) as exc:
        raise PowerAPIError(
            "Invalid NASA POWER response structure."
        ) from exc

    if not isinstance(parameters, dict):
        raise PowerAPIError("Invalid parameter data.")

    dates = sorted(
        set().union(
            *[
                values.keys()
                for values in parameters.values()
                if isinstance(values, dict)
            ]
        )
    )

    records = []

    for day in dates:
        record = {"date": day}

        for name, values in parameters.items():
            raw_value = values.get(day)

            record[name] = (
                None
                if raw_value is None or raw_value == -999
                else float(raw_value)
            )

        records.append(record)

    return records


def calculate_season_summary(
    records: list[dict[str, Any]],
) -> dict[str, float | int | None]:
    """Calculate rainfall and temperature summary."""

    if not records:
        raise ValueError("No weather records provided.")

    rainfall = [
        r["PRECTOTCORR"]
        for r in records
        if r.get("PRECTOTCORR") is not None
    ]

    temperatures = [
        r["T2M"]
        for r in records
        if r.get("T2M") is not None
    ]

    return {
        "rainfall_total_mm": sum(rainfall) if rainfall else None,
        "temperature_mean_c": (
            sum(temperatures) / len(temperatures)
            if temperatures else None
        ),
        "valid_rainfall_days": len(rainfall),
        "valid_temperature_days": len(temperatures),
    }