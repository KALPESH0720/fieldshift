import json
from datetime import date, timedelta

import pytest
import yaml

from fieldshift.common.paths import Layout
from fieldshift.common.region import RegionConfig, load_region, region_cells
from fieldshift.data.soilgrids import SoilPoint, SyntheticSoilProvider
from fieldshift.data.synthetic import SyntheticWeather
from fieldshift.data.weather import WeatherSeries
from fieldshift.data.weather_store import WeatherStore
from fieldshift.features.layer_build import CellInputs, build_cell_features, validate_cells
from fieldshift.features.ndvi import ndvi_variability, season_ndvi
from fieldshift.features.p1_factory import KNOWLEDGE_REGIONS, run_build, run_fetch
from fieldshift.features.run_p1 import P1Error, Providers, build_layer, fetch_weather
from fieldshift.features.season_windows import season_years
from fieldshift.features.thermal import frost_days, growing_degree_days, heat_stress_days, season_tmean
from fieldshift.features.water import (et0_hargreaves, extraterrestrial_radiation, longest_dry_spell, season_et0,
                                       season_rain)
from fieldshift.simulation.soil_params import hydraulic_from_texture
from fieldshift.simulation.water_balance import fallow_moisture_series
from fieldshift.store.memory_store import MemoryStore
from fieldshift.store.models import CellFeatures, SeasonClimate


def _series(tmax, tmin, rain, n=10, lat=18.5):
    d = [date(2020, 6, 1) + timedelta(days=i) for i in range(n)]
    f = lambda v: v if isinstance(v, list) else [v] * n  # noqa: E731
    return WeatherSeries("c", lat, 73.8, "t", False, d, f(tmax), f(tmin), f(rain))


# ---- thermal / water ----
def test_thermal_features_count_correctly():
    w = _series([36, 30, 35, 20], [10, 1, 2, 3], 0.0, n=4)
    idx = range(4)
    assert heat_stress_days(w, idx) == 2          # 36 and 35 reach the threshold
    assert frost_days(w, idx) == 2                # tmin of 1 and 2 are at or below the 2 degree threshold
    assert season_tmean(w, idx) == pytest.approx((23 + 15.5 + 18.5 + 11.5) / 4)
    assert growing_degree_days(_series(30, 20, 0, n=3), range(3)) == pytest.approx(3 * 15.0)


def test_extraterrestrial_radiation_is_in_the_expected_range():
    # FAO-56 worked example 8: 3 September (day 246) at 20 degrees south (-0.35 rad) gives 32.2 MJ m-2 day-1
    assert extraterrestrial_radiation(-20.05, 246) == pytest.approx(32.2, abs=0.15)
    summer = extraterrestrial_radiation(18.5, 172)
    winter = extraterrestrial_radiation(18.5, 355)
    assert 38 < summer < 43 and 25 < winter < 28 and summer > winter
    assert 34 < extraterrestrial_radiation(0.0, 80) < 38
    assert extraterrestrial_radiation(80.0, 355) == pytest.approx(0.0, abs=1e-6)  # polar night


def test_et0_hargreaves_behaviour():
    ra = extraterrestrial_radiation(18.5, 120)
    et = et0_hargreaves(35, 22, ra)
    assert 5 < et < 9
    assert et0_hargreaves(30, 30, ra) == 0.0       # no diurnal range -> the formula gives zero
    assert et0_hargreaves(38, 22, ra) > et0_hargreaves(32, 22, ra)


def test_rain_total_and_dry_spells():
    w = _series(30, 20, [0, 0, 5, 0, 0, 0, 0, 10, 1, 0])
    assert season_rain(w, range(10)) == 16
    assert longest_dry_spell(w, range(10)) == 4          # days 4-7 are dry; rain of 5 and 10 mm break the runs
    w2 = _series(30, 20, [None, 0, 0], n=3)
    assert longest_dry_spell(w2, range(3)) == 2          # a missing day breaks the run
    assert season_et0(w, range(10)) > 0


# ---- season selection / ndvi ----
def test_season_years_requires_coverage():
    region = load_region(KNOWLEDGE_REGIONS / "pune_demo.yaml")
    w = SyntheticWeather().fetch("c", 18.55, 73.85, date(2005, 1, 1), date(2010, 12, 31))
    assert season_years(w, region, "kharif") == [2005, 2006, 2007, 2008, 2009, 2010]
    assert season_years(w, region, "rabi") == [2005, 2006, 2007, 2008, 2009]   # rabi 2010 ends Mar 2011: missing


def test_ndvi_season_means_and_variability():
    region = load_region(KNOWLEDGE_REGIONS / "pune_demo.yaml")
    ndvi = {}
    for y, v in zip(range(2005, 2013), [0.5, 0.6, 0.4, 0.55, 0.65, 0.45, 0.5, 0.6]):
        ndvi[date(y, 7, 1)] = v
        ndvi[date(y, 8, 1)] = v
    means = season_ndvi(ndvi, region, "kharif", range(2005, 2013))
    assert means[2005] == pytest.approx(0.5) and len(means) == 8
    assert 0.1 < ndvi_variability(ndvi, region, range(2005, 2013)) < 0.25
    assert ndvi_variability({}, region, range(2005, 2013)) is None


# ---- layer build ----
@pytest.fixture(scope="module")
def region():
    return load_region(KNOWLEDGE_REGIONS / "pune_demo.yaml")


@pytest.fixture(scope="module")
def weather():
    return SyntheticWeather().fetch("g0.1_185_738", 18.55, 73.85, date(2005, 1, 1), date(2025, 12, 31))


def test_build_cell_features_statistics(region, weather):
    cell = region_cells(region)[0].__class__(738, 185, 0.1)
    soil = SoilPoint(34, 31, 35, 7.2, 6.0)
    hyd = hydraulic_from_texture("clay_loam")
    smap = fallow_moisture_series(weather, hyd, date(2005, 1, 1), date(2024, 12, 31))
    f, warns = build_cell_features(cell, region, CellInputs(weather, soil, smap=smap, synthetic=True), "v1")
    k, r = f.seasons["kharif"], f.seasons["rabi"]
    assert f.synthetic and f.layer_version == "v1" and f.soil_class == "clay_loam" and f.soil_ph == 7.2
    assert (f.sand_pct, f.clay_pct, f.soil_organic_carbon) == (34.0, 35.0, 6.0)
    assert k.rain_mm_dry_year < k.rain_mm_median and 400 < k.rain_mm_median < 900 and r.rain_mm_median < 120
    assert k.stored_water_mm_at_sowing is not None and 0 <= r.stored_water_mm_at_sowing <= 1000 * (0.343 - 0.2056) + 1
    assert 0 <= f.drought_frequency <= 1 and 20 < k.tmean_c < 30 and warns == []
    assert validate_cells([f])["errors"] == []


def test_missing_data_gives_none_and_warnings(region):
    short = SyntheticWeather().fetch("c", 18.55, 73.85, date(2020, 1, 1), date(2021, 12, 31))
    f, warns = build_cell_features(region_cells(region)[0], region, CellInputs(short), "v1")
    assert f.seasons == {} and f.drought_frequency is None and f.soil_class is None
    assert any("usable years" in w for w in warns) and any("no soil" in w for w in warns)


def test_validate_cells_catches_bad_values():
    good = CellFeatures(cell_id="a", layer_version="v", seasons={"kharif": SeasonClimate(
        rain_mm_median=500, rain_mm_dry_year=300, tmean_c=25, stored_water_mm_at_sowing=40)})
    assert validate_cells([good])["errors"] == []
    bad = CellFeatures(cell_id="a", layer_version="v", soil_ph=15, drought_frequency=0.5, seasons={"kharif": SeasonClimate(
        rain_mm_median=300, rain_mm_dry_year=400, tmean_c=60, stored_water_mm_at_sowing=-5)})
    errors = " | ".join(validate_cells([good, bad])["errors"])
    for needle in ("duplicate", "soil_ph", "dry-year rain exceeds", "tmean", "negative stored"):
        assert needle in errors


# ---- P1 orchestration ----
@pytest.fixture
def tiny_regions(tmp_path):
    d = tmp_path / "regions"
    d.mkdir()
    base = yaml.safe_load((KNOWLEDGE_REGIONS / "pune_demo.yaml").read_text())
    base.update(id="tiny", name="tiny", bbox=[73.7, 18.5, 73.9, 18.6], climate_years=[2010, 2024])
    (d / "tiny.yaml").write_text(yaml.safe_dump(base))
    return d


def test_p1_end_to_end_writes_a_layer_the_engine_store_can_read(tmp_path, tiny_regions):
    root = str(tmp_path / "data")
    assert run_fetch("tiny", root, "synthetic", workers=2, regions_dir=tiny_regions) == 0
    report = run_build("tiny", root, "v1", source="synthetic", regions_dir=tiny_regions)
    assert report["n_cells"] == 2 and report["errors"] == [] and report["failed_cells"] == {}
    layer = Layout(root).cells_file("tiny", "v1")
    store = MemoryStore.from_cells_file(layer)
    cell = store.get_cell_features("g0.1_185_738")
    assert cell.synthetic and cell.seasons["rabi"].stored_water_mm_at_sowing > 0
    assert cell.future["ssp245"].temp_delta_c == 1.2
    assert json.loads(open(Layout(root).layer_report("tiny", "v1")).read())["n_cells"] == 2


def test_fetch_reuses_cached_weather_and_records_failures(tmp_path, tiny_regions):
    region = load_region(tiny_regions / "tiny.yaml")
    cells = region_cells(region)
    layout = Layout(str(tmp_path / "d"))
    calls = []

    class Counting(SyntheticWeather):
        def fetch(self, cell_id, lat, lon, start, end):
            calls.append(cell_id)
            if cell_id == cells[1].cell_id:
                raise RuntimeError("download failed")
            return super().fetch(cell_id, lat, lon, start, end)

    fails = fetch_weather(region, layout, Counting(), cells, workers=1)
    assert list(fails) == [cells[1].cell_id] and "download failed" in fails[cells[1].cell_id]
    assert WeatherStore(layout, "tiny").has(cells[0].cell_id)
    calls.clear()
    fetch_weather(region, layout, Counting(), cells, workers=1)
    assert calls == [cells[1].cell_id]             # the cached cell is not fetched again
    assert len(fetch_weather(region, layout, Counting(), cells, workers=1, refetch=True)) == 1 and len(calls) == 3


def test_build_layer_fails_when_too_many_cells_are_missing(tmp_path, tiny_regions):
    region = load_region(tiny_regions / "tiny.yaml")
    layout = Layout(str(tmp_path / "d"))
    providers = Providers(SyntheticWeather(), SyntheticSoilProvider(), synthetic=True)
    with pytest.raises(P1Error, match="cells failed"):
        build_layer(region, layout, providers, "v1")      # no weather was downloaded
    assert json.loads(open(layout.layer_report("tiny", "v1")).read())["errors"]


def test_unknown_sources_are_rejected(tmp_path):
    from fieldshift.features.p1_factory import make_soil, make_weather
    with pytest.raises(ValueError):
        make_weather("nope")
    with pytest.raises(ValueError):
        make_soil("csv", None)
    with pytest.raises(ValueError):
        make_soil("raster", None)
    assert isinstance(RegionConfig, type)
