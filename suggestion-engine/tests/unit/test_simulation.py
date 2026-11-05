from datetime import date, timedelta

import pytest

from fieldshift.common.config import load_settings
from fieldshift.data.synthetic import SyntheticWeather
from fieldshift.data.weather import WeatherSeries
from fieldshift.simulation.crop_params import CropSim, load_crop_sim
from fieldshift.simulation.indicators import build_indicator, yearly_scores
from fieldshift.simulation.soil_params import (TEXTURE_CENTROIDS, hydraulic_from_texture, hydraulic_properties,
                                               om_from_oc)
from fieldshift.simulation.water_balance import (fallow, fallow_moisture_series, perturb, simulate_season,
                                                 simulate_sequence)

CYCLE = ("kharif", "rabi")


@pytest.fixture(scope="module")
def sim():
    return load_crop_sim(load_settings().knowledge_dir)


@pytest.fixture(scope="module")
def weather():
    return SyntheticWeather().fetch("g0.1_185_738", 18.55, 73.85, date(2005, 1, 1), date(2025, 12, 31))


def const_weather(rain, tmax=33.0, tmin=21.0, start=date(2020, 1, 1), days=500, lat=18.5):
    d = [start + timedelta(days=i) for i in range(days)]
    return WeatherSeries("c", lat, 73.8, "t", False, d, [tmax] * days, [tmin] * days, [rain] * days)


# ---------------------------------------------------------------- soil hydraulics
def test_hydraulic_properties_are_physically_ordered_for_all_textures():
    for texture in TEXTURE_CENTROIDS:
        h = hydraulic_from_texture(texture)
        assert 0 < h.theta_wp < h.theta_fc < h.theta_sat < 0.75 and h.ksat_mm_h > 0, texture


def test_hydraulic_trends_follow_texture():
    sand, loam, clay = (hydraulic_from_texture(t) for t in ("sand", "loam", "clay"))
    assert sand.theta_wp < loam.theta_wp < clay.theta_wp
    assert sand.theta_fc < loam.theta_fc < clay.theta_fc
    assert sand.ksat_mm_h > loam.ksat_mm_h > clay.ksat_mm_h
    assert 0.05 < loam.theta_fc - loam.theta_wp < 0.20        # available water of a loam, m3/m3
    assert hydraulic_properties(40, 20, 4.0).theta_fc > hydraulic_properties(40, 20, 1.0).theta_fc


def test_hydraulic_guards_and_units():
    for sand in range(0, 101, 10):
        for clay in range(0, 101 - sand, 10):
            h = hydraulic_properties(sand, clay)
            assert h.theta_fc > h.theta_wp
    with pytest.raises(ValueError):
        hydraulic_properties(80, 40)
    with pytest.raises(ValueError):
        hydraulic_from_texture("gravel")
    assert om_from_oc(None) == 2.0 and om_from_oc(10.0) == pytest.approx(1.724)


# ---------------------------------------------------------------- crop parameters
def test_every_crop_has_simulation_parameters_and_sowing_dates(kb, sim):
    for cid, crop in kb.crops.items():
        assert cid in sim, f"{cid} has no simulation parameters"
        for season in crop.seasons:
            assert season in sim[cid].sowing, f"{cid} has no sowing date for {season}"
        assert abs(sim[cid].season_days - crop.duration_days) <= 15, cid


def test_kc_curve_and_root_depth(sim):
    c = sim["maize"]
    assert c.kc_on(0) == 0.30 and c.kc_on(19) == 0.30
    assert c.kc_on(20) == pytest.approx(0.30) and c.kc_on(35) == pytest.approx(0.30 + 0.9 * 15 / 30)
    assert c.kc_on(50) == 1.20 and c.kc_on(84) == 1.20
    assert c.kc_on(85) == 1.20 and c.kc_on(105) == 0.60 and c.kc_on(500) == 0.60
    assert c.root_depth_on(0) == pytest.approx(0.3) and c.root_depth_on(50) == pytest.approx(1.0)
    assert 0.3 <= sim["onion"].root_depth_on(0) <= sim["onion"].root_depth_m + 1e-9   # shallow crop never exceeds its maximum


def test_crop_sim_validation():
    ok = dict(id="x", kc=[0.4, 1.1, 0.5], stage_days=[10, 10, 10, 10], root_depth_m=1.0, depletion_fraction=0.5, ky=1.0,
              sowing={"kharif": (6, 25)})
    CropSim.model_validate(ok)
    for patch in ({"kc": [1, 2]}, {"stage_days": [1, 2, 3]}, {"stage_days": [1, 2, 3, 0]}):
        with pytest.raises(ValueError):
            CropSim.model_validate({**ok, **patch})


# ---------------------------------------------------------------- water balance
def test_full_irrigation_removes_stress(sim):
    hyd = hydraulic_from_texture("clay_loam")
    r = simulate_season(const_weather(0.0), sim["maize"], date(2020, 2, 1), hyd, 0.5, "full")
    assert r.relative_yield == pytest.approx(1.0) and r.eta_mm == pytest.approx(r.etc_mm) and r.irrigation_mm > 0


def test_dry_weather_hurts_rainfed_crops_and_irrigation_ranks_the_modes(sim):
    hyd = hydraulic_from_texture("clay_loam")
    w = const_weather(0.0)
    rainfed = simulate_season(w, sim["maize"], date(2020, 2, 1), hyd, 0.5, "rainfed")
    limited = simulate_season(w, sim["maize"], date(2020, 2, 1), hyd, 0.5, "limited", limited_mm=100)
    full = simulate_season(w, sim["maize"], date(2020, 2, 1), hyd, 0.5, "full")
    assert rainfed.relative_yield < 0.6 and rainfed.irrigation_mm == 0
    assert rainfed.relative_yield < limited.relative_yield < full.relative_yield
    assert limited.irrigation_mm <= 100 + 1e-9


def test_plenty_of_rain_gives_full_yield_and_water_is_conserved(sim):
    hyd = hydraulic_from_texture("clay_loam")
    r = simulate_season(const_weather(8.0), sim["maize"], date(2020, 2, 1), hyd, 0.5)
    assert r.relative_yield == pytest.approx(1.0) and r.eta_mm == pytest.approx(r.etc_mm)
    assert 0 <= r.end_fraction <= 1


def test_more_stored_water_and_deeper_soil_help(sim):
    clay, sand = hydraulic_from_texture("clay"), hydraulic_from_texture("sand")
    w = const_weather(1.0)
    start = date(2020, 2, 1)
    dry_start = simulate_season(w, sim["sorghum"], start, clay, 0.1).relative_yield
    wet_start = simulate_season(w, sim["sorghum"], start, clay, 1.0).relative_yield
    assert wet_start > dry_start
    assert simulate_season(w, sim["sorghum"], start, clay, 1.0).relative_yield > \
        simulate_season(w, sim["sorghum"], start, sand, 1.0).relative_yield   # clay stores more available water


def test_higher_ky_means_bigger_loss(sim):
    hyd = hydraulic_from_texture("clay_loam")
    w = const_weather(0.5)
    base = sim["soybean"]
    tolerant = base.model_copy(update={"ky": 0.5})
    sensitive = base.model_copy(update={"ky": 1.4})
    a = simulate_season(w, tolerant, date(2020, 2, 1), hyd, 0.5).relative_yield
    b = simulate_season(w, sensitive, date(2020, 2, 1), hyd, 0.5).relative_yield
    assert 0 <= b < a <= 1


def test_missing_weather_raises_keyerror_and_sequence_returns_none(sim, weather):
    hyd = hydraulic_from_texture("clay_loam")
    with pytest.raises(KeyError):
        simulate_season(const_weather(1.0, days=30), sim["maize"], date(2020, 1, 1), hyd, 0.5)
    assert simulate_sequence(weather, [sim["soybean"], sim["chickpea"]], "kharif-2025", CYCLE, hyd, 0.5) is None  # rabi 2025 needs 2026 data
    assert simulate_sequence(weather, [sim["soybean"], sim["chickpea"]], "kharif-2024", CYCLE, hyd, 0.5) is not None


def test_sequence_chains_seasons_and_carries_water(sim, weather):
    hyd = hydraulic_from_texture("clay_loam")
    res = simulate_sequence(weather, [sim["soybean"], sim["chickpea"]], "kharif-2012", CYCLE, hyd, 0.5)
    assert [r.crop for r in res] == ["soybean", "chickpea"] and [r.season for r in res] == ["kharif-2012", "rabi-2012"]
    assert res[0].sowing == date(2012, 6, 25) and res[0].end == date(2012, 6, 25) + timedelta(days=99)
    assert res[1].sowing == date(2012, 10, 25) and res[1].delay_days == 0 and res[0].end < res[1].sowing
    assert all(0 <= r.relative_yield <= 1 for r in res)


def test_long_crop_delays_the_next_sowing(sim, weather):
    hyd = hydraulic_from_texture("clay_loam")
    res = simulate_sequence(weather, [sim["pigeonpea"], sim["wheat"]], "kharif-2012", CYCLE, hyd, 0.5)
    assert res[0].end == date(2012, 12, 1)                       # 160 days from 25 June
    assert res[1].delay_days == 27 and res[1].sowing == date(2012, 12, 2)


def test_unknown_sowing_season_is_an_error(sim, weather):
    hyd = hydraulic_from_texture("clay_loam")
    with pytest.raises(ValueError, match="no sowing date"):
        simulate_sequence(weather, [sim["wheat"]], "kharif-2012", CYCLE, hyd, 0.5)


def test_fallow_recharges_with_rain_and_loses_little_when_dry():
    hyd = hydraulic_from_texture("clay_loam")
    sixty_days_end = date(2020, 1, 1) + timedelta(days=59)
    wet = fallow(const_weather(10.0), date(2020, 1, 1), sixty_days_end, hyd, 0.1)
    dry = fallow(const_weather(0.0), date(2020, 1, 1), sixty_days_end, hyd, 0.8)
    assert wet == pytest.approx(1.0) and 0.5 < dry < 0.8
    assert fallow(const_weather(0.0), date(2020, 2, 1), date(2020, 1, 1), hyd, 0.3) == 0.3   # empty period


def test_fallow_moisture_series_stays_between_wilting_point_and_field_capacity(weather):
    hyd = hydraulic_from_texture("clay_loam")
    s = fallow_moisture_series(weather, hyd, date(2010, 1, 1), date(2011, 12, 31))
    assert len(s) == 730 and all(hyd.theta_wp - 1e-9 <= v <= hyd.theta_fc + 1e-9 for v in s.values())
    assert s[date(2010, 11, 1)] > s[date(2010, 6, 1)]                      # the monsoon recharges the profile


def test_perturb_applies_climate_change_factors_without_touching_the_original(weather):
    p = perturb(weather, temp_delta_c=1.5, rain_change_pct=10.0)
    i = next(k for k, v in enumerate(weather.rain) if v and v > 5)
    assert p.tmax[i] == pytest.approx(weather.tmax[i] + 1.5) and p.rain[i] == pytest.approx(weather.rain[i] * 1.1)
    assert weather.tmax[i] != p.tmax[i] and len(p) == len(weather)


# ---------------------------------------------------------------- indicators
def test_indicator_statistics():
    base = {y: 0.5 + 0.03 * (y - 2000) for y in range(2000, 2012)}     # 0.50 ... 0.83
    ind = build_indicator("a>b", base)
    assert ind.water_score_median == pytest.approx(0.665, abs=1e-3)
    assert ind.water_score_pessimistic < ind.water_score_median and 0 < ind.yield_factor_pessimistic < 1
    worse_future = {y: 0.3 for y in range(2040, 2052)}
    assert build_indicator("a>b", base, worse_future).water_score_pessimistic < ind.water_score_pessimistic


def test_indicator_needs_enough_years_and_handles_zero_median():
    assert build_indicator("a", {2000: 0.5, 2001: 0.6}) is None
    zero = build_indicator("a", {y: 0.0 for y in range(2000, 2010)})
    assert zero.yield_factor_pessimistic == 1.0 and zero.water_score_median == 0.0


def test_yearly_scores_average_the_slots(sim, weather):
    hyd = hydraulic_from_texture("clay_loam")
    res = simulate_sequence(weather, [sim["soybean"], sim["chickpea"]], "kharif-2012", CYCLE, hyd, 0.5)
    assert yearly_scores({2012: res})[2012] == pytest.approx((res[0].relative_yield + res[1].relative_yield) / 2)
