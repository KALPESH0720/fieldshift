"""Drift alerts: observed moisture or vegetation well below what this cell normally shows."""
from __future__ import annotations

from typing import Optional

from ..store.models import Alert
from .anomalies import classify_low
from .sowing_window import SowingStatus

SEVERITY = {"watch": "watch", "act": "act"}


def drift_alerts(cell_id: str, crop: Optional[str], season: str,
                 observed: dict[str, float], history: dict[str, list[float]]) -> list[Alert]:
    """`observed` and `history` use the keys 'soil_moisture' and 'ndvi'."""
    out: list[Alert] = []
    codes = {"soil_moisture": "MOISTURE_BELOW_EXPECTED", "ndvi": "NDVI_BELOW_EXPECTED"}
    for key, code in codes.items():
        if key not in observed or key not in history:
            continue
        a = classify_low(observed[key], history[key])
        if a is None or a.level == "ok":
            continue
        out.append(Alert(cell_id=cell_id, crop=crop, type="drift", severity=SEVERITY[a.level], code=code,
                         valid_from=None, valid_to=None,
                         params={"season": season, "observed": round(a.value, 4), "median": round(a.median, 4),
                                 "percentile": a.percentile}))
    return out


def sowing_alert(cell_id: str, crop: str, season: str, status: SowingStatus) -> Optional[Alert]:
    if status.state == "open" or status.state == "not_open":
        return None
    severity = "act" if status.state == "closed" else "watch"
    code = "SOWING_WINDOW_CLOSED" if status.state == "closed" else "SOWING_WINDOW_CLOSING"
    return Alert(cell_id=cell_id, crop=crop, type="sowing_window", severity=severity, code=code,
                 valid_to=status.latest_sowing.isoformat(),
                 params={"season": season, "days_left": max(status.days_left, 0),
                         "onset": status.onset.isoformat() if status.onset else None})
