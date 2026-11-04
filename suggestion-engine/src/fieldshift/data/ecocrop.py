"""EcoCrop-style crop requirement data loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


class EcoCropError(Exception):
    """Raised when crop requirement data is invalid."""


class EcoCropDatabase:
    """Load and query crop suitability information."""

    REQUIRED_FIELDS = {
        "id",
        "seasons",
        "temp_c",
        "rain_mm",
        "ph",
        "water_need_mm",
    }

    def __init__(self, crops: list[dict[str, Any]]):
        self.crops: dict[str, dict[str, Any]] = {}

        for crop in crops:
            self._validate_crop(crop)

            crop_id = str(crop["id"]).strip().lower()

            if crop_id in self.crops:
                raise EcoCropError(
                    f"Duplicate crop ID: {crop_id}"
                )

            self.crops[crop_id] = crop

    @classmethod
    def from_file(cls, file_path: str | Path) -> "EcoCropDatabase":
        """Load crop data from YAML or JSON."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)

        content = path.read_text(encoding="utf-8")

        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(content)
        elif path.suffix.lower() == ".json":
            data = json.loads(content)
        else:
            raise EcoCropError(
                "Only YAML and JSON files are supported."
            )

        if isinstance(data, dict):
            data = data.get("crops", [])

        if not isinstance(data, list):
            raise EcoCropError(
                "Crop data must contain a list of crops."
            )

        return cls(data)

    @classmethod
    def _validate_crop(cls, crop: dict[str, Any]) -> None:
        if not isinstance(crop, dict):
            raise EcoCropError("Each crop must be a dictionary.")

        missing = cls.REQUIRED_FIELDS - set(crop)

        if missing:
            raise EcoCropError(
                f"Missing crop fields: {sorted(missing)}"
            )

        for field in ("temp_c", "rain_mm", "ph"):
            values = crop[field]

            if (
                not isinstance(values, list)
                or len(values) != 4
                or not all(
                    isinstance(value, (int, float))
                    for value in values
                )
            ):
                raise EcoCropError(
                    f"{field} must contain four numeric limits."
                )

            if values != sorted(values):
                raise EcoCropError(
                    f"{field} limits must be in ascending order."
                )

        if not isinstance(crop["seasons"], list):
            raise EcoCropError("Seasons must be a list.")

        if not isinstance(crop["water_need_mm"], (int, float)):
            raise EcoCropError(
                "Water requirement must be numeric."
            )

        if crop["water_need_mm"] <= 0:
            raise EcoCropError(
                "Water requirement must be positive."
            )

    def get_crop(self, crop_id: str) -> dict[str, Any] | None:
        """Retrieve one crop."""
        return self.crops.get(crop_id.strip().lower())

    def get_all_crops(self) -> list[dict[str, Any]]:
        """Return all available crops."""
        return list(self.crops.values())

    def get_crops_by_season(
        self,
        season: str,
    ) -> list[dict[str, Any]]:
        """Find crops suitable for a particular season."""
        season = season.strip().lower()

        return [
            crop
            for crop in self.crops.values()
            if season in [
                item.lower() for item in crop["seasons"]
            ]
        ]

    def check_ph(
        self,
        crop_id: str,
        soil_ph: float,
    ) -> bool:
        """Check whether soil pH is within absolute crop limits."""
        crop = self.get_crop(crop_id)

        if crop is None:
            raise KeyError(f"Unknown crop: {crop_id}")

        lower, _, _, upper = crop["ph"]

        return lower < soil_ph < upper

    def check_temperature(
        self,
        crop_id: str,
        temperature: float,
    ) -> bool:
        """Check crop temperature suitability."""
        crop = self.get_crop(crop_id)

        if crop is None:
            raise KeyError(f"Unknown crop: {crop_id}")

        lower, _, _, upper = crop["temp_c"]

        return lower < temperature < upper

    def check_rainfall(
        self,
        crop_id: str,
        rainfall: float,
    ) -> bool:
        """Check crop rainfall suitability."""
        crop = self.get_crop(crop_id)

        if crop is None:
            raise KeyError(f"Unknown crop: {crop_id}")

        lower, _, _, upper = crop["rain_mm"]

        return lower < rainfall < upper