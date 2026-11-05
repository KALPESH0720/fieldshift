"""Soil fields of a CellFeatures record from a SoilPoint."""
from __future__ import annotations

from typing import Any, Optional

from ..data.soilgrids import SoilPoint


def soil_fields(point: Optional[SoilPoint]) -> dict[str, Any]:
    if point is None:
        return {}
    return {
        "soil_class": point.texture,
        "soil_ph": None if point.ph is None else round(point.ph, 2),
        "soil_organic_carbon": None if point.oc_g_kg is None else round(point.oc_g_kg, 2),
        "sand_pct": round(point.sand_pct, 1),
        "clay_pct": round(point.clay_pct, 1),
    }
