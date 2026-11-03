"""MODIS NDVI (MOD13Q1, via AppEEARS). Product and layer names are configuration (verify versions)."""
from __future__ import annotations

from datetime import date

from .appeears import find_column, read_point_csv

PRODUCT = "MOD13Q1.061"
LAYER = "_250m_16_days_NDVI"
SCALE = 0.0001
VALID_RAW = (-2000.0, 10000.0)


def parse_ndvi(csv_text: str, layer: str = LAYER) -> dict[str, dict[date, float]]:
    """cell_id -> {date: NDVI}. Values outside the valid range (fill -3000) are dropped. Already scaled."""
    rows = read_point_csv(csv_text)
    if not rows:
        return {}
    col = find_column(rows[0], layer)
    if col is None:
        raise ValueError(f"no column containing '{layer}' in {list(rows[0])}")
    out: dict[str, dict[date, float]] = {}
    for r in rows:
        try:
            raw = float(r[col])
        except (TypeError, ValueError):
            continue
        if not VALID_RAW[0] <= raw <= VALID_RAW[1]:
            continue
        out.setdefault(r["ID"], {})[date.fromisoformat(r["Date"][:10])] = raw * SCALE
    return out
