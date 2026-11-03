"""Pipeline P3 (season monitor): turn fresh observations into alerts.

For every cell with a logged planting this season it checks the sowing window (rain so far) and
drift (soil moisture, NDVI against the cell's history). Observations come from an
`ObservationSource`; the real one (recent POWER rain, SMAP, NDVI) is wired in the pipeline and was
not run against live data from the development sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Protocol

from ..common.logging import get_logger
from ..common.seasons import parse_season
from ..simulation.crop_params import CropSim
from ..store.base import Store
from ..store.models import Alert
from .drift import drift_alerts, sowing_alert
from .sowing_window import sowing_status

log = get_logger("fieldshift.p3")


@dataclass
class Observation:
    rain: dict[date, float] = field(default_factory=dict)       # daily rain this season
    soil_moisture: Optional[float] = None                        # latest, m3/m3
    ndvi: Optional[float] = None


@dataclass
class Baseline:
    soil_moisture: list[float] = field(default_factory=list)    # same time of year, previous years
    ndvi: list[float] = field(default_factory=list)


class ObservationSource(Protocol):
    def observation(self, cell_id: str, season: str, today: date) -> Optional[Observation]: ...
    def baseline(self, cell_id: str, season: str, today: date) -> Baseline: ...


def _key(a: Alert) -> tuple:
    return (a.cell_id, a.crop, a.code, a.params.get("season"))


def run_p3(store: Store, source: ObservationSource, crop_sim: dict[str, CropSim], season: str, today: date) -> list[Alert]:
    """Write new alerts to the store and return them. Existing identical alerts are not duplicated."""
    name, year = parse_season(season)
    planted = [a for a in store.list_actions() if a.season == season and a.cell_id]
    seen = {(c, crop) for c, crop in ((a.cell_id, a.planted_crop) for a in planted)}
    new: list[Alert] = []
    for cell_id, crop in sorted(seen):
        obs = source.observation(cell_id, season, today)
        if obs is None:
            log.warning("no observation for %s", cell_id)
            continue
        alerts: list[Alert] = []
        params = crop_sim.get(crop)
        if params and name in params.sowing:
            planned = date(year, *params.sowing[name])
            status = sowing_status(today, obs.rain, date(year, *params.sowing[name]).replace(day=1), planned)
            a = sowing_alert(cell_id, crop, season, status)
            if a:
                alerts.append(a)
        base = source.baseline(cell_id, season, today)
        observed = {k: v for k, v in (("soil_moisture", obs.soil_moisture), ("ndvi", obs.ndvi)) if v is not None}
        alerts += drift_alerts(cell_id, crop, season, observed, {"soil_moisture": base.soil_moisture, "ndvi": base.ndvi})
        existing = {_key(a) for a in store.list_alerts(cell_id)}
        for a in alerts:
            if _key(a) not in existing:
                store.put_alert(a)
                new.append(a)
    return new
