"""Save and load per-cell weather series under raw/power/{region}/{cell_id}.json (local or gs://)."""
from __future__ import annotations

from ..common import io
from ..common.paths import Layout
from .weather import WeatherSeries


class WeatherStore:
    def __init__(self, layout: Layout, region: str):
        self.layout = layout
        self.region = region

    def path(self, cell_id: str) -> str:
        return self.layout.weather(self.region, cell_id)

    def has(self, cell_id: str) -> bool:
        return io.exists(self.path(cell_id))

    def save(self, series: WeatherSeries) -> str:
        p = self.path(series.cell_id)
        io.write_json(p, series.to_dict(), indent=None)
        return p

    def load(self, cell_id: str) -> WeatherSeries:
        return WeatherSeries.from_dict(io.read_json(self.path(cell_id)))
