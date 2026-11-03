import json
from datetime import date

import httpx
import pytest

from fieldshift.common.http import HttpClient
from fieldshift.common.region import RegionConfig
from fieldshift.data.appeears import AppeearsClient, AppeearsError
from fieldshift.data.crop_history import build_regional_prior
from fieldshift.data.ecocrop import compare_with_crop_table, load_ecocrop_csv
from fieldshift.data.modis import parse_ndvi
from fieldshift.data.nex_gddp import NexGddpReader, compute_delta, delta_from_reader, season_stats
from fieldshift.data.power import PowerClient
from fieldshift.data.smap import available_water_mm, parse_rootzone, stored_water_at_sowing
from fieldshift.data.soilgrids import (CsvSoilProvider, RasterSoilProvider, SoilPoint, SyntheticSoilProvider,
                                       texture_class)
from fieldshift.data.synthetic import SyntheticWeather
from fieldshift.data.weather import WeatherSeries
from fieldshift.grid.cells import Cell


# ------------------------------------------------------------------ weather container
def _ws(n=5, start=date(2020, 1, 1)):
    from datetime import timedelta
    d = [start + timedelta(days=i) for i in range(n)]
    return WeatherSeries("c", 18.5, 73.8, "t", False, d, [30.0] * n, [20.0] * n, [0.0] * n)


def test_weather_series_validation_window_coverage_roundtrip():
    w = _ws(10)
    assert len(w) == 10 and w.rad == [None] * 10
    assert list(w.window(date(2020, 1, 3), date(2020, 1, 5))) == [2, 3, 4]
    assert w.coverage(date(2020, 1, 1), date(2020, 1, 10)) == 1.0
    w.rain[0] = None
    assert w.coverage(date(2020, 1, 1), date(2020, 1, 10)) == pytest.approx(0.9)
    assert w.tmean(1) == 25.0
    assert WeatherSeries.from_dict(json.loads(json.dumps(w.to_dict()))).rain[0] is None
    with pytest.raises(ValueError):
        WeatherSeries("c", 0, 0, "t", False, [date(2020, 1, 1)], [1.0, 2.0], [1.0], [1.0])
    with pytest.raises(ValueError):
        WeatherSeries("c", 0, 0, "t", False, [date(2020, 1, 2), date(2020, 1, 1)], [1, 1], [1, 1], [1, 1])


def test_concat_removes_overlap_and_sorts():
    a, b = _ws(5, date(2020, 1, 1)), _ws(5, date(2020, 1, 4))
    out = WeatherSeries.concat([b, a])
    assert len(out) == 8 and out.dates[0] == date(2020, 1, 1) and out.dates[-1] == date(2020, 1, 8)


# ------------------------------------------------------------------ POWER
def _power_payload(days, fill_day=None):
    keys = [f"2020010{d}" for d in days]
    def col(v): return {k: (-999 if k == fill_day else v) for k in keys}
    return {"properties": {"parameter": {"T2M_MAX": col(31.5), "T2M_MIN": col(19.0), "PRECTOTCORR": col(2.5),
                                         "ALLSKY_SFC_SW_DWN": col(18.0)}}}


def test_power_parse_converts_fill_values_to_none():
    s = PowerClient.parse(_power_payload([1, 2, 3], fill_day="20200102"), "cell", 18.5, 73.8)
    assert s.dates == [date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)]
    assert s.tmax[1] is None and s.rain[1] is None and s.tmax[0] == 31.5 and s.source == "nasa_power"


def test_power_params_and_chunked_fetch():
    p = PowerClient.build_params(18.55, 73.85, date(2020, 1, 1), date(2020, 1, 31))
    assert p["community"] == "AG" and p["start"] == "20200101" and p["end"] == "20200131"
    assert p["latitude"] == "18.5500" and "T2M_MAX" in p["parameters"]

    seen = []

    def handler(req):
        q = dict(req.url.params)
        seen.append((q["start"], q["end"]))
        year = int(q["start"][:4])
        return httpx.Response(200, json={"properties": {"parameter": {
            "T2M_MAX": {f"{year}0101": 30.0}, "T2M_MIN": {f"{year}0101": 20.0},
            "PRECTOTCORR": {f"{year}0101": 1.0}, "ALLSKY_SFC_SW_DWN": {f"{year}0101": 15.0}}}})

    client = PowerClient(http=HttpClient(transport=httpx.MockTransport(handler)), chunk_years=3)
    s = client.fetch("c", 18.5, 73.8, date(2010, 1, 1), date(2016, 12, 31))
    assert seen == [("20100101", "20121231"), ("20130101", "20151231"), ("20160101", "20161231")]
    assert [d.year for d in s.dates] == [2010, 2013, 2016]


def test_power_rejects_unexpected_payload():
    with pytest.raises(ValueError):
        PowerClient.parse({"messages": ["bad"]}, "c", 0, 0)


# ------------------------------------------------------------------ synthetic weather
def test_synthetic_weather_is_deterministic_and_plausible():
    a = SyntheticWeather().fetch("g0.1_185_738", 18.55, 73.85, date(2010, 1, 1), date(2012, 12, 31))
    b = SyntheticWeather().fetch("g0.1_185_738", 18.55, 73.85, date(2010, 1, 1), date(2012, 12, 31))
    assert a.to_dict() == b.to_dict() and a.synthetic
    assert all(t > m for t, m in zip(a.tmax, a.tmin))
    assert min(a.rain) >= 0 and 15 < max(a.tmax) < 45
    kharif = sum(a.rain[i] for i in a.window(date(2011, 6, 1), date(2011, 10, 31)))
    assert 250 < kharif < 1100
    other = SyntheticWeather().fetch("other", 18.55, 73.85, date(2010, 1, 1), date(2010, 12, 31))
    assert other.rain != a.rain[:365]


# ------------------------------------------------------------------ soil
def test_every_sand_silt_clay_combination_has_a_texture_class():
    for sand in range(0, 101, 2):
        for silt in range(0, 101 - sand, 2):
            assert texture_class(sand, silt, 100 - sand - silt)


@pytest.mark.parametrize("sand,silt,clay,expected", [
    (90, 5, 5, "sand"), (80, 15, 5, "loamy_sand"), (65, 25, 10, "sandy_loam"), (40, 40, 20, "loam"),
    (20, 65, 15, "silt_loam"), (10, 85, 5, "silt"), (60, 15, 25, "sandy_clay_loam"), (33, 34, 33, "clay_loam"),
    (10, 55, 35, "silty_clay_loam"), (50, 5, 45, "sandy_clay"), (5, 50, 45, "silty_clay"), (20, 20, 60, "clay"),
])
def test_texture_class_known_points(sand, silt, clay, expected):
    assert texture_class(sand, silt, clay) == expected


def test_texture_class_normalises_and_rejects_empty():
    assert texture_class(4, 4, 2) == texture_class(40, 40, 20)
    with pytest.raises(ValueError):
        texture_class(0, 0, 0)


def test_csv_and_synthetic_soil_providers(tmp_path):
    f = tmp_path / "soil.csv"
    f.write_text("cell_id,sand_pct,silt_pct,clay_pct,ph,oc_g_kg\ng0.1_185_738,35,30,35,7.1,6.5\ng0.1_1_1,40,40,20,,\n")
    p = CsvSoilProvider(f)
    pt = p.sample(Cell(738, 185, 0.1))
    assert pt == SoilPoint(35, 30, 35, 7.1, 6.5) and pt.texture == "clay_loam"
    assert p.sample(Cell(1, 1, 0.1)).ph is None
    assert p.sample(Cell(5, 5, 0.1)) is None
    s = SyntheticSoilProvider()
    assert s.sample(Cell(738, 185, 0.1)) == s.sample(Cell(738, 185, 0.1))
    q = s.sample(Cell(7, 7, 0.1))
    assert abs(q.sand_pct + q.silt_pct + q.clay_pct - 100) < 1.5 and 6.0 <= q.ph <= 8.0


def _tif(path, value, crs="EPSG:4326", nodata=-32768, patch=None):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    data = np.full((100, 100), value, dtype="int16")   # 0.01 degree pixels over lon 73-74, lat 18-19
    if patch:
        data[patch] = nodata
    with rasterio.open(path, "w", driver="GTiff", height=100, width=100, count=1, dtype="int16", crs=crs,
                       transform=from_origin(73.0, 19.0, 0.01, 0.01), nodata=nodata) as ds:
        ds.write(data, 1)
    return str(path)


def test_raster_soil_provider_converts_units_and_skips_nodata(tmp_path):
    paths = {"sand": _tif(tmp_path / "sand.tif", 350), "silt": _tif(tmp_path / "silt.tif", 300),
             "clay": _tif(tmp_path / "clay.tif", 350, patch=(slice(40, 45), slice(None))),  # northern half of the cell is nodata
             "phh2o": _tif(tmp_path / "ph.tif", 70), "soc": _tif(tmp_path / "soc.tif", 80)}
    cell = Cell(ix=738, iy=185, size_deg=0.1)  # lon 73.8-73.9, lat 18.5-18.6 -> inside the raster
    pt = RasterSoilProvider(paths).sample(cell)
    assert (pt.sand_pct, pt.silt_pct, pt.clay_pct, pt.ph, pt.oc_g_kg) == pytest.approx((35.0, 30.0, 35.0, 7.0, 8.0))
    assert pt.texture == "clay_loam"
    outside = RasterSoilProvider(paths).sample(Cell(ix=900, iy=185, size_deg=0.1))
    assert outside is None  # no valid pixels there


def test_raster_soil_provider_rejects_wrong_crs_and_missing_layers(tmp_path):
    bad = {k: _tif(tmp_path / f"{k}.tif", 300, crs="EPSG:3857") for k in ("sand", "silt", "clay")}
    with pytest.raises(ValueError, match="EPSG:4326"):
        RasterSoilProvider(bad).sample(Cell(738, 185, 0.1))
    with pytest.raises(ValueError):
        RasterSoilProvider({"sand": "x"})


# ------------------------------------------------------------------ AppEEARS
class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _appeears_transport(statuses, files=None, calls=None):
    files = files if files is not None else [{"file_id": "f1", "file_name": "task-MOD-results.csv"},
                                             {"file_id": "f2", "file_name": "readme.txt"}]
    it = iter(statuses)

    def handler(req):
        path = req.url.path
        if calls is not None:
            calls.append((req.method, path, req.headers.get("authorization")))
        if path.endswith("/login"):
            assert req.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"token": "tok123"})
        if path.endswith("/task") and req.method == "POST":
            body = json.loads(req.content)
            assert body["task_type"] == "point"
            assert body["params"]["dates"] == [{"startDate": "01-01-2020", "endDate": "12-31-2020"}]
            assert body["params"]["layers"] == [{"product": "P.1", "layer": "L"}]
            assert body["params"]["coordinates"][0] == {"id": "c1", "longitude": 73.85, "latitude": 18.55, "category": "cell"}
            return httpx.Response(202, json={"task_id": "T1"})
        if "/status/" in path:
            return httpx.Response(200, json={"task_id": "T1", "status": next(it)})
        if path.endswith("/bundle/T1"):
            return httpx.Response(200, json={"files": files})
        if path.endswith("/bundle/T1/f1"):
            return httpx.Response(200, text="ID,Date\nc1,2020-01-01\n")
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def _client_for(transport, clock=None):
    clock = clock or FakeClock()
    return AppeearsClient(http=HttpClient(transport=transport), poll_seconds=30, timeout_seconds=100,
                          sleep=clock.sleep, clock=clock), clock


def test_appeears_full_flow_polls_and_sends_bearer_token():
    calls = []
    c, clock = _client_for(_appeears_transport(["pending", "processing", "done"], calls=calls))
    assert c.login("u", "p") == "tok123"
    text = c.run_point_task("task", [{"id": "c1", "lat": 18.55, "lon": 73.85}], [("P.1", "L")],
                            date(2020, 1, 1), date(2020, 12, 31))
    assert text.startswith("ID,Date") and clock.t == 60  # two waits of 30 s
    assert all(a == "Bearer tok123" for m, p, a in calls if not p.endswith("/login"))


def test_appeears_error_status_missing_results_and_timeout():
    c, _ = _client_for(_appeears_transport(["error"]))
    c.token = "t"
    with pytest.raises(AppeearsError, match="error"):
        c.run_point_task("task", [{"id": "c1", "lat": 18.55, "lon": 73.85}], [("P.1", "L")], date(2020, 1, 1), date(2020, 12, 31))

    c, _ = _client_for(_appeears_transport(["done"], files=[{"file_id": "x", "file_name": "readme.txt"}]))
    c.token = "t"
    with pytest.raises(AppeearsError, match="no results CSV"):
        c.run_point_task("task", [{"id": "c1", "lat": 18.55, "lon": 73.85}], [("P.1", "L")], date(2020, 1, 1), date(2020, 12, 31))

    c, _ = _client_for(_appeears_transport(["processing"] * 10))
    c.token = "t"
    with pytest.raises(AppeearsError, match="still"):
        c.wait("T1")


def test_appeears_requires_login():
    c, _ = _client_for(_appeears_transport([]))
    with pytest.raises(AppeearsError, match="not logged in"):
        c.status("T1")


# ------------------------------------------------------------------ SMAP / MODIS parsing and conversion
SMAP_CSV = """ID,Category,Latitude,Longitude,Date,SPL4SMGP_008_sm_rootzone
c1,cell,18.5,73.8,2020-06-01,0.30
c1,cell,18.5,73.8,2020-06-01,0.34
c1,cell,18.5,73.8,2020-06-02,-9999
c2,cell,18.5,73.9,2020-06-01,0.25
"""


def test_parse_rootzone_averages_days_and_drops_fill_values():
    out = parse_rootzone(SMAP_CSV)
    assert out["c1"] == {date(2020, 6, 1): pytest.approx(0.32)} and out["c2"][date(2020, 6, 1)] == 0.25
    with pytest.raises(ValueError):
        parse_rootzone(SMAP_CSV, layer="not_there")
    assert parse_rootzone("ID,Date\n") == {}


def test_available_water_and_stored_water_at_sowing():
    assert available_water_mm(0.30, 0.20, 0.35) == pytest.approx(100.0)
    assert available_water_mm(0.50, 0.20, 0.35) == pytest.approx(150.0)   # capped at field capacity
    assert available_water_mm(0.10, 0.20, 0.35) == 0.0
    series = {date(y, 6, 1): 0.30 for y in (2010, 2011, 2012)}
    series[date(2012, 6, 1)] = 0.35
    series[date(2013, 1, 1)] = 0.9   # far from sowing: ignored
    assert stored_water_at_sowing(series, (6, 1), range(2010, 2014), 0.20, 0.35) == pytest.approx(100.0)
    assert stored_water_at_sowing(series, (7, 1), range(2010, 2014), 0.20, 0.35) is None


def test_parse_ndvi_scales_and_drops_fill():
    csv_text = ("ID,Category,Latitude,Longitude,Date,MOD13Q1_061__250m_16_days_NDVI\n"
                "c1,cell,1,1,2020-06-01,5000\nc1,cell,1,1,2020-06-17,-3000\nc1,cell,1,1,2020-07-03,7000\n")
    assert parse_ndvi(csv_text) == {"c1": {date(2020, 6, 1): pytest.approx(0.5), date(2020, 7, 3): pytest.approx(0.7)}}


# ------------------------------------------------------------------ NEX-GDDP
def _region():
    return RegionConfig.model_validate({
        "id": "r", "name": "r", "bbox": [73, 18, 74, 19], "climate_years": [2000, 2001],
        "seasons": {"kharif": {"start": [6, 1], "end": [10, 31]}, "rabi": {"start": [11, 1], "end": [3, 31]}}})


def test_nex_path_and_compute_delta():
    r = NexGddpReader("ACCESS-CM2")
    assert r.path("ssp245", "tas", 2050) == (
        "s3://nex-gddp-cmip6/NEX-GDDP-CMIP6/ACCESS-CM2/ssp245/r1i1p1f1/tas/tas_day_ACCESS-CM2_ssp245_r1i1p1f1_gn_2050.nc")
    d = compute_delta({2000: (24.0, 600.0), 2001: (26.0, 800.0)}, {2050: (26.5, 770.0)})
    assert d.temp_delta_c == 1.5 and d.rain_change_pct == pytest.approx(10.0)
    assert compute_delta({}, {2050: (1, 1)}) is None


def test_season_stats_needs_complete_seasons():
    from datetime import timedelta
    start = date(2000, 1, 1)
    dates = [start + timedelta(days=i) for i in range(366 + 365)]      # 2000 and 2001, complete
    stats = season_stats(dates, [25.0] * len(dates), [2.0] * len(dates), _region(), range(2000, 2002))
    assert set(stats) == {2000}      # 2001's rabi runs into March 2002, which is missing
    t, rain = stats[2000]
    # kharif Jun 1-Oct 31 = 153 days; rabi Nov 1 2000 - Mar 31 2001 = 151 days; 2 mm each day
    assert t == 25.0 and rain == pytest.approx(2.0 * (153 + 151))


def _write_nc(tmp_path, var, scenario, year, value):
    import numpy as np
    import pandas as pd
    import xarray as xr
    times = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    arr = np.full((len(times), 2, 2), value, dtype="float32")
    ds = xr.Dataset({var: (("time", "lat", "lon"), arr)},
                    coords={"time": times, "lat": [18.375, 18.625], "lon": [73.625, 73.875]})
    p = tmp_path / f"{scenario}_{var}_{year}.nc"
    ds.to_netcdf(p, engine="h5netcdf")
    return p


def test_nex_reader_reads_points_and_computes_delta_from_files(tmp_path):
    for year in (2000, 2001):
        _write_nc(tmp_path, "tas", "historical", year, 300.0)
        _write_nc(tmp_path, "pr", "historical", year, 1.0e-5)
    for year in (2050, 2051):
        _write_nc(tmp_path, "tas", "ssp245", year, 301.5)
        _write_nc(tmp_path, "pr", "ssp245", year, 1.1e-5)
    template = str(tmp_path / "{scenario}_{var}_{year}.nc")
    reader = NexGddpReader("M", template=template)
    dates, values = reader.read_point("historical", "tas", 2000, 18.6, 73.9)
    assert len(dates) == 366 and dates[0] == date(2000, 1, 1) and values[0] == pytest.approx(300.0)
    d = delta_from_reader(reader, _region(), 18.55, 73.85, "ssp245", range(2000, 2002), range(2050, 2052))
    assert d.temp_delta_c == pytest.approx(1.5, abs=0.01) and d.rain_change_pct == pytest.approx(10.0, abs=0.1)


# ------------------------------------------------------------------ EcoCrop and crop history
def test_ecocrop_comparison_flags_large_differences(tmp_path, kb):
    f = tmp_path / "eco.csv"
    header = "name,tmin_abs,tmin_opt,tmax_opt,tmax_abs,rain_min_abs,rain_min_opt,rain_max_opt,rain_max_abs,ph_min_abs,ph_min_opt,ph_max_opt,ph_max_abs\n"
    soy = kb.crop("soybean")
    close = ",".join(str(x) for x in soy.temp_c + soy.rain_mm + soy.ph)
    far = ",".join(str(x) for x in [t + 8 for t in kb.crop("wheat").temp_c] + kb.crop("wheat").rain_mm + kb.crop("wheat").ph)
    f.write_text(header + f"soybean,{close}\nwheat,{far}\nunknown_crop,{close}\n")
    found = compare_with_crop_table(load_ecocrop_csv(f), kb.crops)
    assert [(d.crop, d.quantity) for d in found] == [("wheat", "temp_c")] and found[0].max_difference == 8.0


def test_regional_prior_shares():
    rows = [{"season": "kharif", "crop": "soybean", "area_ha": 300}, {"season": "kharif", "crop": "maize", "area_ha": 100},
            {"season": "kharif", "crop": "soybean", "area_ha": 100}, {"season": "rabi", "crop": "wheat", "area_ha": 50},
            {"season": "rabi", "crop": "quinoa", "area_ha": 50}]
    prior = build_regional_prior(rows, known_crops={"soybean", "maize", "wheat"})
    assert prior == {"kharif": {"maize": 0.2, "soybean": 0.8}, "rabi": {"wheat": 1.0}}
    with pytest.raises(ValueError):
        build_regional_prior([{"season": "kharif", "crop": "x", "area_ha": -1}])
