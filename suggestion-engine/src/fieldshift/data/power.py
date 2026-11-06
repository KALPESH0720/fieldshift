"""NASA POWER daily point client.

Built from the POWER documentation (endpoint, parameters, response layout). It has NOT been run
against the live service from the development sandbox: run `python scripts/check_live_access.py`
on your machine to confirm. Resolution is coarse, so values are regional estimates for a cell.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from ..common.http import HttpClient
from .weather import WeatherSeries

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = ("T2M_MAX", "T2M_MIN", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN")
FILL_VALUE = -999.0


def _clean(v: Any) -> Optional[float]:
    if v is None:
        return None
    v = float(v)
    return None if v <= FILL_VALUE + 0.5 else v


class PowerClient:
    def __init__(self, http: Optional[HttpClient] = None, base_url: str = BASE_URL, chunk_years: int = 5):
        self.http = http or HttpClient()
        self.base_url = base_url
        self.chunk_years = chunk_years

    @staticmethod
    def build_params(lat: float, lon: float, start: date, end: date) -> dict[str, str]:
        return {
            "parameters": ",".join(PARAMETERS),
            "community": "AG",
            "longitude": f"{lon:.4f}",
            "latitude": f"{lat:.4f}",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "format": "JSON",
        }

    @staticmethod
    def parse(payload: dict[str, Any], cell_id: str, lat: float, lon: float) -> WeatherSeries:
        try:
            params = payload["properties"]["parameter"]
        except (KeyError, TypeError):
            raise ValueError(f"unexpected POWER response: {str(payload)[:200]}")
        keys = sorted(params["T2M_MAX"])
        dates = [date(int(k[:4]), int(k[4:6]), int(k[6:8])) for k in keys]
        rad = params.get("ALLSKY_SFC_SW_DWN", {})
        return WeatherSeries(
            cell_id=cell_id, lat=lat, lon=lon, source="nasa_power", synthetic=False, dates=dates,
            tmax=[_clean(params["T2M_MAX"][k]) for k in keys],
            tmin=[_clean(params["T2M_MIN"].get(k)) for k in keys],
            rain=[_clean(params["PRECTOTCORR"].get(k)) for k in keys],
            rad=[_clean(rad.get(k)) for k in keys],
        )

    def fetch(self, cell_id: str, lat: float, lon: float, start: date, end: date) -> WeatherSeries:
        parts = []
        year = start.year
        while year <= end.year:
            last_year = min(year + self.chunk_years - 1, end.year)
            s = max(start, date(year, 1, 1))
            e = min(end, date(last_year, 12, 31))
            payload = self.http.get_json(self.base_url, params=self.build_params(lat, lon, s, e))
            parts.append(self.parse(payload, cell_id, lat, lon))
            year = last_year + 1
        return WeatherSeries.concat(parts)
