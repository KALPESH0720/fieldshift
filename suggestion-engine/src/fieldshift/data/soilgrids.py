"""ISRIC SoilGrids soil data integration."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any


BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"


class SoilGridsError(Exception):
    """SoilGrids data retrieval error."""


PROPERTIES = (
    "phh2o",
    "soc",
    "clay",
    "sand",
    "silt",
)

DEPTHS = (
    "0-5cm",
    "5-15cm",
    "15-30cm",
    "30-60cm",
)


def fetch_soil_data(
    latitude: float,
    longitude: float,
    properties: tuple[str, ...] = PROPERTIES,
    timeout: int = 30,
) -> dict[str, Any]:
    """Fetch soil properties from SoilGrids."""

    if not -90 <= latitude <= 90:
        raise ValueError("Invalid latitude.")

    if not -180 <= longitude <= 180:
        raise ValueError("Invalid longitude.")

    invalid = set(properties) - set(PROPERTIES)

    if invalid:
        raise ValueError(
            f"Unsupported soil properties: {sorted(invalid)}"
        )

    params = {
        "lon": longitude,
        "lat": latitude,
        "property": list(properties),
        "depth": list(DEPTHS),
        "value": ["mean"],
    }

    url = f"{BASE_URL}?{urlencode(params, doseq=True)}"

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "FieldShift/0.1",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )

    except Exception as exc:
        raise SoilGridsError(
            f"Unable to retrieve SoilGrids data: {exc}"
        ) from exc

    return result


def extract_soil_properties(
    response: dict[str, Any],
) -> dict[str, Any]:
    """Extract mean soil measurements from SoilGrids."""

    layers = response.get("properties", {}).get("layers", [])

    if not isinstance(layers, list):
        raise SoilGridsError("Invalid SoilGrids layers.")

    output = {}

    for layer in layers:
        name = layer.get("name")
        depths = layer.get("depths", [])

        if not name or not depths:
            continue

        values = []

        for depth in depths:
            value = depth.get("values", {}).get("mean")

            if value is not None and value != -32768:
                values.append(float(value))

        output[name] = (
            sum(values) / len(values)
            if values else None
        )

    # SoilGrids pH is reported in pH × 10.
    if output.get("phh2o") is not None:
        output["ph"] = output["phh2o"] / 10.0

    # SoilGrids organic carbon is reported in g/kg.
    if output.get("soc") is not None:
        output["organic_carbon_g_per_kg"] = output["soc"]

    return output


def get_soil_summary(
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    """Fetch and return a normalized soil summary."""

    raw = fetch_soil_data(latitude, longitude)

    return extract_soil_properties(raw)