"""Crop history processing for FieldShift."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

@dataclass(frozen=True)
class CropHistoryRecord:
    season: str
    crop: str

def validate_season(season: str) -> bool:
    """Validate season format, for example kharif-2027."""
    if not isinstance(season, str):
        return False

    parts = season.strip().lower().split("-")

    return (
        len(parts) == 2
        and parts[0].isalpha()
        and parts[1].isdigit()
        and len(parts[1]) == 4
    )


def normalize_crop(crop: str) -> str:
    """Normalize crop names."""
    if not isinstance(crop, str) or not crop.strip():
        raise ValueError("Crop name cannot be empty.")

    return " ".join(crop.strip().lower().split())


def process_history(
    records: Iterable[dict[str, Any] | CropHistoryRecord],
    limit: int = 3,
) -> list[CropHistoryRecord]:

    if limit < 1:
        raise ValueError("History limit must be at least 1.")

    processed = []

    for record in records:
        if isinstance(record, CropHistoryRecord):
            season = record.season.strip().lower()
            crop = normalize_crop(record.crop)
        else:
            season = str(record.get("season", "")).strip().lower()
            crop = normalize_crop(record.get("crop", ""))

        if not validate_season(season):
            raise ValueError(f"Invalid season: {season}")

        processed.append(
            CropHistoryRecord(
                season=season,
                crop=crop,
            )
        )

    # Sort by year, keeping original order for equal years.
    processed.sort(
        key=lambda item: int(item.season.split("-")[1]),
        reverse=True,
    )

    return processed[:limit]

def get_recent_crops(
    records: Iterable[CropHistoryRecord],
) -> list[str]:
    """Return crop names from newest to oldest."""
    return [record.crop for record in records]


def get_crop_frequency(
    records: Iterable[CropHistoryRecord],
) -> dict[str, int]:
    """Count how frequently each crop appears."""
    return dict(
        Counter(record.crop for record in records)
    )

def has_recent_crop(
    records: Iterable[CropHistoryRecord],
    crop: str,
    seasons: int = 2,
) -> bool:
    """Check whether a crop was recently cultivated."""
    if seasons < 1:
        raise ValueError("Seasons must be at least 1.")

    target = normalize_crop(crop)

    recent = list(records)[:seasons]

    return any(record.crop == target for record in recent)

def get_previous_crop(
    records: Iterable[CropHistoryRecord],
) -> str | None:
    """Return the most recently cultivated crop."""
    records = list(records)

    return records[0].crop if records else None

def summarize_history(
    records: Iterable[CropHistoryRecord],
) -> dict[str, Any]:
    """Generate a summary for recommendation processing."""
    records = list(records)

    return {
        "total_records": len(records),
        "crops": get_recent_crops(records),
        "frequency": get_crop_frequency(records),
        "previous_crop": get_previous_crop(records),
        "repeated_crops": [
            crop
            for crop, count in get_crop_frequency(records).items()
            if count > 1
        ],
    }