from __future__ import annotations

import math

from .cells import Cell


def snap(lat: float, lon: float, size_deg: float) -> Cell:
    """Snap a point to its regular-grid cell. The cell id is stable for a given size."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("lat/lon out of range")
    return Cell(
        ix=math.floor(round(lon / size_deg, 9)),
        iy=math.floor(round(lat / size_deg, 9)),
        size_deg=size_deg,
    )
