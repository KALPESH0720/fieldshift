
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping


class GridPipelineError(ValueError):
    """Invalid grid pipeline input."""


@dataclass
class GridLayerBundle:
    grid_id: str
    latitude: float
    longitude: float
    weather: dict[str, Any] = field(default_factory=dict)
    soil: dict[str, Any] = field(default_factory=dict)
    satellite: dict[str, Any] = field(default_factory=dict)
    crop_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_id": self.grid_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "weather": self.weather,
            "soil": self.soil,
            "satellite": self.satellite,
            "crop_history": self.crop_history,
            "metadata": self.metadata,
        }


def _validate_coordinate(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GridPipelineError(
            f"{name} must be numeric."
        ) from exc

    if not isfinite(number):
        raise GridPipelineError(
            f"{name} must be finite."
        )

    return number


def validate_grid_input(data: Mapping[str, Any]) -> None:
    """Validate required spatial input fields."""

    if "latitude" not in data or "longitude" not in data:
        raise GridPipelineError(
            "Latitude and longitude are required."
        )

    latitude = _validate_coordinate(
        data["latitude"], "latitude"
    )

    longitude = _validate_coordinate(
        data["longitude"], "longitude"
    )

    if not -90 <= latitude <= 90:
        raise GridPipelineError(
            "Latitude must be between -90 and 90."
        )

    if not -180 <= longitude <= 180:
        raise GridPipelineError(
            "Longitude must be between -180 and 180."
        )


def prepare_grid_layers(
    data: Mapping[str, Any],
) -> GridLayerBundle:
    """
    Prepare input layers for one agricultural location.

    Expected input:
        latitude, longitude
        grid_id (optional)
        weather (optional mapping)
        soil (optional mapping)
        satellite (optional mapping)
        crop_history (optional list)
        metadata (optional mapping)
    """

    validate_grid_input(data)

    latitude = _validate_coordinate(
        data["latitude"], "latitude"
    )

    longitude = _validate_coordinate(
        data["longitude"], "longitude"
    )

    grid_id = str(
        data.get("grid_id")
        or f"grid_{latitude:.4f}_{longitude:.4f}"
    )

    weather = dict(data.get("weather") or {})
    soil = dict(data.get("soil") or {})
    satellite = dict(data.get("satellite") or {})
    crop_history = list(data.get("crop_history") or [])
    metadata = dict(data.get("metadata") or {})

    if not all(isinstance(item, Mapping) for item in crop_history):
        raise GridPipelineError(
            "Each crop history record must be a mapping."
        )

    metadata.update({
        "latitude": latitude,
        "longitude": longitude,
        "layer_availability": {
            "weather": bool(weather),
            "soil": bool(soil),
            "satellite": bool(satellite),
            "crop_history": bool(crop_history),
        },
    })

    return GridLayerBundle(
        grid_id=grid_id,
        latitude=latitude,
        longitude=longitude,
        weather=weather,
        soil=soil,
        satellite=satellite,
        crop_history=crop_history,
        metadata=metadata,
    )


def run_p1_grid_pipeline(
    data: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute P1 grid preparation."""

    bundle = prepare_grid_layers(data)

    return {
        "stage": "p1_grid_layers",
        "status": "success",
        "grid": bundle.to_dict(),
    }
