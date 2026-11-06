"""Providers of future climate change factors (deltas against the historical baseline)."""
from __future__ import annotations

from typing import Optional, Protocol

from ..common.region import RegionConfig
from ..data.nex_gddp import NexGddpReader, delta_from_reader
from ..grid.cells import Cell
from ..store.models import FutureDelta


class FutureDeltaProvider(Protocol):
    def delta(self, cell: Cell, scenario: str) -> Optional[FutureDelta]: ...


class StaticDeltaProvider:
    """Same deltas for every cell (e.g. a regional value taken from a published projection)."""

    def __init__(self, deltas: dict[str, FutureDelta]):
        self.deltas = deltas

    def delta(self, cell: Cell, scenario: str) -> Optional[FutureDelta]:
        return self.deltas.get(scenario)


class NexGddpDeltaProvider:
    def __init__(self, reader: NexGddpReader, region: RegionConfig,
                 baseline_years: range = range(1995, 2015), future_years: range = range(2041, 2061)):
        self.reader, self.region = reader, region
        self.baseline_years, self.future_years = baseline_years, future_years

    def delta(self, cell: Cell, scenario: str) -> Optional[FutureDelta]:
        return delta_from_reader(self.reader, self.region, cell.center_lat, cell.center_lon, scenario,
                                 self.baseline_years, self.future_years)
