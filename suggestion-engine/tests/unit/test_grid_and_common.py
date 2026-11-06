import inspect

import pytest

from fieldshift.common.seasons import next_seasons, season_key
from fieldshift.common.units import to_acres, to_inr_per_quintal
from fieldshift.grid.cache_key import build_cache_key, sequence_key
from fieldshift.grid.cells import parse_cell_id
from fieldshift.grid.snap import snap


def test_snap_is_stable_and_groups_nearby_points():
    a = snap(18.52, 73.85, 0.1)
    b = snap(18.549, 73.801, 0.1)
    c = snap(18.61, 73.85, 0.1)
    assert a.cell_id == b.cell_id
    assert a.cell_id != c.cell_id


def test_snap_handles_negative_coordinates_and_roundtrip():
    c = snap(-12.34, -45.67, 0.1)
    assert parse_cell_id(c.cell_id) == c


def test_snap_rejects_out_of_range():
    with pytest.raises(ValueError):
        snap(95, 10, 0.1)


def test_cache_key_changes_with_versions_but_has_no_weight_argument():
    args = ("g0.1_185_738", "clay", "ssp245", "0.1.0", "p1", "r1", "rainfed")
    k1 = build_cache_key(*args)
    assert k1 == build_cache_key(*args)
    assert k1 != build_cache_key(*args[:5], "r2", args[6])
    params = inspect.signature(build_cache_key).parameters
    assert not any("weight" in p or "price" in p for p in params)


def test_sequence_key():
    assert sequence_key(["soybean", "wheat"]) == "soybean>wheat"


def test_next_seasons_rolls_the_year():
    cycle = ("kharif", "rabi")
    assert next_seasons("kharif-2027", 3, cycle) == ["kharif-2027", "rabi-2027", "kharif-2028"]
    assert next_seasons("rabi-2027", 2, cycle) == ["rabi-2027", "kharif-2028"]
    with pytest.raises(ValueError):
        next_seasons("summer-2027", 2, cycle)


def test_season_ordering():
    assert season_key("kharif-2026") < season_key("rabi-2026") < season_key("kharif-2027")


def test_units():
    assert to_acres(1, "hectare") == pytest.approx(2.4711, abs=1e-3)
    assert to_acres(40, "guntha") == pytest.approx(1.0)
    assert to_inr_per_quintal(48, "INR/kg") == 4800
    assert to_inr_per_quintal(48000, "INR/tonne") == 4800
    with pytest.raises(ValueError):
        to_inr_per_quintal(1, "usd/bushel")
