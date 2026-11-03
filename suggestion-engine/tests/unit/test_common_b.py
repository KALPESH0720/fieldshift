import os

import httpx
import pytest

from fieldshift.common import io
from fieldshift.common.http import HttpClient, HttpError
from fieldshift.common.paths import Layout
from fieldshift.common.region import RegionConfig, find_region, load_region, region_cells
from fieldshift.common.stats import cv, mean, median, percentile
from fieldshift.features.p1_factory import KNOWLEDGE_REGIONS


# ---- stats ----
def test_stats_ignore_missing_and_interpolate():
    assert percentile([1, 2, 3, 4, 5], 20) == pytest.approx(1.8)
    assert percentile([None, 4.0], 90) == 4.0
    assert median([None, 1, 3]) == 2.0
    assert mean([None, None]) is None and percentile([], 50) is None
    assert cv([5]) is None and cv([0, 0]) is None
    assert cv([1, 2, 3]) == pytest.approx(0.4082, abs=1e-3)
    with pytest.raises(ValueError):
        percentile([1, 2], 120)


# ---- io ----
def test_io_roundtrip_is_atomic_and_creates_folders(tmp_path):
    p = str(tmp_path / "a" / "b" / "x.json")
    assert not io.exists(p)
    io.write_json(p, {"k": [1, 2]})
    assert io.read_json(p) == {"k": [1, 2]} and io.exists(p)
    io.write_json(p, {"k": 3})
    assert io.read_json(p) == {"k": 3}
    assert [f for f in os.listdir(os.path.dirname(p)) if f.endswith(".tmp")] == []


def test_gcs_path_helpers():
    assert io.is_gcs("gs://b/x") and not io.is_gcs("/tmp/x")
    assert io._split_gcs("gs://bucket/a/b.json") == ("bucket", "a/b.json")
    with pytest.raises(ValueError):
        io._split_gcs("gs://bucket-only")


# ---- paths ----
def test_layout_paths_for_local_and_gcs_roots():
    for root in ("/data/", "gs://bkt"):
        lay = Layout(root)
        base = root.rstrip("/")
        assert lay.weather("r1", "c1") == f"{base}/raw/power/r1/c1.json"
        assert lay.cells_file("r1", "v2") == f"{base}/layers/r1/v2/cells.json"
        assert lay.run_file("p2", "run9", "out.json") == f"{base}/runs/p2/run9/out.json"
        assert lay.models_dir("abc") == f"{base}/models/abc"


# ---- http ----
def _client(handler, sleeps=None):
    return HttpClient(transport=httpx.MockTransport(handler), backoff=1.0, retries=3,
                      sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def test_http_retries_then_succeeds_with_exponential_backoff():
    calls, sleeps = [], []

    def handler(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(200, json={"ok": True})

    assert _client(handler, sleeps).get_json("http://x/y") == {"ok": True}
    assert len(calls) == 3 and sleeps == [1.0, 2.0]


def test_http_client_error_is_not_retried_and_exhaustion_raises():
    calls = []

    def not_found(req):
        calls.append(1)
        return httpx.Response(404, text="nope")

    with pytest.raises(HttpError) as e:
        _client(not_found).get_json("http://x")
    assert e.value.status == 404 and len(calls) == 1

    always = []

    def down(req):
        always.append(1)
        return httpx.Response(500)

    with pytest.raises(HttpError):
        _client(down).get_json("http://x")
    assert len(always) == 4  # 1 try + 3 retries


def test_http_retries_network_errors():
    n = []

    def flaky(req):
        n.append(1)
        if len(n) == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json=1)

    assert _client(flaky).get_json("http://x") == 1


# ---- region ----
def test_demo_region_loads_and_enumerates_cells():
    region = load_region(KNOWLEDGE_REGIONS / "pune_demo.yaml")
    cells = region_cells(region)
    ids = [c.cell_id for c in cells]
    assert len(ids) == len(set(ids)) == 126
    min_lon, min_lat, max_lon, max_lat = region.bbox
    assert all(min_lat <= c.center_lat <= max_lat and min_lon <= c.center_lon <= max_lon for c in cells)
    assert {"g0.1_185_738", "g0.1_181_745", "g0.1_187_734"} <= set(ids)  # the synthetic fixture cells


def test_season_windows_handle_year_crossing():
    region = load_region(KNOWLEDGE_REGIONS / "pune_demo.yaml")
    ks, ke = region.seasons["kharif"].dates(2026)
    rs, re_ = region.seasons["rabi"].dates(2026)
    assert (ks.isoformat(), ke.isoformat()) == ("2026-06-01", "2026-10-31")
    assert (rs.isoformat(), re_.isoformat()) == ("2026-11-01", "2027-03-31")
    assert region.seasons["rabi"].crosses_year and not region.seasons["kharif"].crosses_year


@pytest.mark.parametrize("patch", [
    {"bbox": [74, 18, 73, 19]}, {"bbox": [1, 2, 3]}, {"climate_years": [2024, 2005]}, {"cell_size_deg": 0},
    {"seasons": {"kharif": {"start": [13, 1], "end": [10, 31]}}},
])
def test_region_validation_rejects_bad_config(patch):
    base = {"id": "x", "name": "x", "bbox": [73.3, 18.0, 74.7, 18.9], "climate_years": [2005, 2024],
            "seasons": {"kharif": {"start": [6, 1], "end": [10, 31]}}}
    RegionConfig.model_validate(base)
    with pytest.raises(ValueError):
        RegionConfig.model_validate({**base, **patch})


def test_find_region_missing_returns_none(tmp_path):
    assert find_region(tmp_path, "nope") is None
