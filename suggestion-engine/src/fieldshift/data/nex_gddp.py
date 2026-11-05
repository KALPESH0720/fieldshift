"""Future climate change factors from NEX-GDDP-CMIP6.

The pure functions (season statistics, delta computation) are tested. `NexGddpReader` opens yearly
NetCDF files with xarray; it is tested on small synthetic NetCDF files, NOT against the live
bucket. The file-name template below is the commonly documented pattern (verify against the
bucket listing, versions such as `_v2.0` exist for some models).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Optional

from ..common.region import RegionConfig
from ..common.stats import mean
from ..store.models import FutureDelta

DEFAULT_TEMPLATE = (
    "s3://nex-gddp-cmip6/NEX-GDDP-CMIP6/{model}/{scenario}/{variant}/{var}/"
    "{var}_day_{model}_{scenario}_{variant}_{grid}_{year}.nc"
)
KELVIN = 273.15
SECONDS_PER_DAY = 86400.0


class NexGddpReader:
    """Reads one variable for one grid point and year. Returns (dates, values) in model units."""

    def __init__(self, model: str, variant: str = "r1i1p1f1", grid: str = "gn",
                 template: str = DEFAULT_TEMPLATE, opener: Optional[Callable] = None):
        self.model, self.variant, self.grid, self.template = model, variant, grid, template
        self._opener = opener

    def path(self, scenario: str, var: str, year: int) -> str:
        return self.template.format(model=self.model, scenario=scenario, variant=self.variant,
                                    var=var, grid=self.grid, year=year)

    def read_point(self, scenario: str, var: str, year: int, lat: float, lon: float):
        try:
            import xarray as xr
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("pip install xarray h5netcdf (and s3fs for s3:// paths)") from e
        opener = self._opener or (lambda p: xr.open_dataset(p, engine="h5netcdf"))
        ds = opener(self.path(scenario, var, year))
        lon360 = lon % 360.0  # the dataset uses 0..360 longitudes
        point = ds[var].sel(lat=lat, lon=lon360, method="nearest")
        dates = [date(int(t.dt.year), int(t.dt.month), int(t.dt.day)) for t in point["time"]]
        values = [float(v) for v in point.values]
        ds.close()
        return dates, values


def season_stats(
    dates: list[date], tmean_c: list[float], rain_mm: list[float], region: RegionConfig, years: range
) -> dict[int, tuple[float, float]]:
    """year -> (mean temperature over the region's seasons, total rain over the region's seasons)."""
    out: dict[int, tuple[float, float]] = {}
    index = {d: i for i, d in enumerate(dates)}
    for y in years:
        temps, rain = [], 0.0
        complete = True
        for win in region.seasons.values():
            s, e = win.dates(y)
            d = s
            while d <= e:
                i = index.get(d)
                if i is None:
                    complete = False
                    break
                temps.append(tmean_c[i])
                rain += rain_mm[i]
                d += timedelta(days=1)
            if not complete:
                break
        if complete and temps:
            out[y] = (sum(temps) / len(temps), rain)
    return out


def compute_delta(baseline: dict[int, tuple[float, float]], future: dict[int, tuple[float, float]]) -> Optional[FutureDelta]:
    """Temperature difference (deg C) and rainfall change (%) between two sets of years."""
    if not baseline or not future:
        return None
    t0, t1 = mean(v[0] for v in baseline.values()), mean(v[0] for v in future.values())
    r0, r1 = mean(v[1] for v in baseline.values()), mean(v[1] for v in future.values())
    pct = None if not r0 else (r1 / r0 - 1.0) * 100.0
    return FutureDelta(temp_delta_c=round(t1 - t0, 3), rain_change_pct=None if pct is None else round(pct, 2))


def delta_from_reader(
    reader: NexGddpReader, region: RegionConfig, lat: float, lon: float, scenario: str,
    baseline_years: range, future_years: range, baseline_scenario: str = "historical",
) -> Optional[FutureDelta]:
    def collect(scn: str, years: range) -> dict[int, tuple[float, float]]:
        dates_all, t_all, r_all = [], [], []
        for y in years:
            d_t, tas = reader.read_point(scn, "tas", y, lat, lon)
            d_p, pr = reader.read_point(scn, "pr", y, lat, lon)
            if d_t != d_p:
                raise ValueError(f"tas and pr dates differ for {scn} {y}")
            dates_all += d_t
            t_all += [v - KELVIN for v in tas]
            r_all += [v * SECONDS_PER_DAY for v in pr]
        # season_stats needs seasons that cross into y+1, so ask only for years whose data exists
        return season_stats(dates_all, t_all, r_all, region, years)

    return compute_delta(collect(baseline_scenario, baseline_years), collect(scenario, future_years))
