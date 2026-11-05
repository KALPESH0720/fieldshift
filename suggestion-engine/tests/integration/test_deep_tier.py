"""Engine <-> batch side: P1 layer -> engine -> cache miss -> P2 -> indicators -> refined answer."""
import inspect
import json

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from fieldshift.api.main import create_app
from fieldshift.common.config import Settings, load_pipeline_settings
from fieldshift.common.http import HttpClient
from fieldshift.common.paths import Layout
from fieldshift.common.region import load_region
from fieldshift.data.weather_store import WeatherStore
from fieldshift.engine.recommend import Engine
from fieldshift.features.p1_factory import KNOWLEDGE_REGIONS, run_build, run_fetch
from fieldshift.simulation.crop_params import load_crop_sim
from fieldshift.simulation.launcher import LocalLauncher, VertexLauncher, build_launcher
from fieldshift.simulation.p2_remote import run_remote
from fieldshift.simulation.run_p2 import P2Config, P2Error, process_job, publish_via_api, run_job
from fieldshift.store.memory_store import MemoryStore
from fieldshift.store.models import Indicator, Job


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    base = tmp_path_factory.mktemp("deep")
    regions = base / "regions"
    regions.mkdir()
    cfg = yaml.safe_load((KNOWLEDGE_REGIONS / "pune_demo.yaml").read_text())
    cfg.update(id="tiny", name="tiny", bbox=[73.8, 18.5, 73.9, 18.6], climate_years=[2010, 2024])
    (regions / "tiny.yaml").write_text(yaml.safe_dump(cfg))
    root = str(base / "data")
    assert run_fetch("tiny", root, "synthetic", workers=1, regions_dir=regions) == 0
    run_build("tiny", root, "v1", source="synthetic", regions_dir=regions)
    return {"root": root, "regions": regions, "layer": Layout(root).cells_file("tiny", "v1"),
            "region": load_region(regions / "tiny.yaml")}


@pytest.fixture
def parts(env, kb, settings):
    store = MemoryStore.from_cells_file(env["layer"])
    launcher = LocalLauncher(store, WeatherStore(Layout(env["root"]), "tiny"), load_crop_sim(settings.knowledge_dir),
                             P2Config(region=env["region"], cycle=settings.season_cycle))
    engine = Engine(kb, store, settings, launcher=launcher)
    return engine, launcher, TestClient(create_app(engine))


def test_local_launcher_turns_a_fast_answer_into_a_refined_one(parts, base_request):
    engine, launcher, client = parts
    first = client.post("/v1/recommend", json=base_request).json()
    assert first["status"] == "fast" and first["job_id"] and "SYNTHETIC_CELL_DATA" in first["notes"]
    launcher.join()
    job = client.get(f"/v1/jobs/{first['job_id']}").json()
    assert job["status"] == "done" and job["start_season"] == "kharif-2027" and job["irrigation"] == "rainfed"

    stored = engine.store.get_indicators(job["cache_key"])
    assert stored and all(0 <= i.water_score_pessimistic <= i.water_score_median <= 1 for i in stored.values())
    second = client.post("/v1/recommend", json=base_request).json()
    assert second["status"] == "refined" and second["job_id"] is None
    assert len(launcher.threads) == 1                       # the second request did not start another run
    by_seq_first = {tuple(o["crop_sequence"]): o["scores"]["water_risk"] for o in first["options"]}
    by_seq_second = {tuple(o["crop_sequence"]): o["scores"]["water_risk"] for o in second["options"]}
    shared = set(by_seq_first) & set(by_seq_second)
    assert shared and any(by_seq_first[k] != by_seq_second[k] for k in shared)   # simulation changed the water score


def test_process_job_handles_unknown_crops_and_missing_inputs(env, parts, settings):
    engine, _, _ = parts
    store = engine.store
    ws = WeatherStore(Layout(env["root"]), "tiny")
    sim = load_crop_sim(settings.knowledge_dir)
    cfg = P2Config(region=env["region"])
    job = Job(cache_key="k", request_id="r", cell_id="g0.1_185_738", sequences=["soybean>chickpea", "quinoa>wheat"],
              start_season="kharif-2027", irrigation="rainfed", soil_class="clay_loam", scenario="ssp245")
    inds, warns = process_job(job, store, ws, sim, cfg)
    assert [i.sequence for i in inds] == ["soybean>chickpea"] and any("quinoa" in w for w in warns)
    with pytest.raises(P2Error, match="no start_season"):
        process_job(job.model_copy(update={"start_season": None}), store, ws, sim, cfg)
    with pytest.raises(P2Error, match="no feature layer"):
        process_job(job.model_copy(update={"cell_id": "nowhere"}), store, ws, sim, cfg)


def test_irrigation_improves_simulated_scores(env, parts, settings):
    engine, _, _ = parts
    ws, sim, cfg = WeatherStore(Layout(env["root"]), "tiny"), load_crop_sim(settings.knowledge_dir), P2Config(region=env["region"])
    out = {}
    for irr in ("rainfed", "limited", "full"):
        job = Job(cache_key=irr, request_id="r", cell_id="g0.1_185_738", sequences=["soybean>chickpea"],
                  start_season="kharif-2027", irrigation=irr, soil_class="clay_loam", scenario="ssp245")
        out[irr] = process_job(job, engine.store, ws, sim, cfg)[0][0].water_score_median
    assert out["rainfed"] < out["limited"] <= out["full"] and out["full"] == pytest.approx(1.0)


def test_run_job_records_failure(env, parts, settings):
    engine, _, _ = parts
    job, _ = engine.store.create_job_if_absent(Job(cache_key="bad", request_id="r", cell_id="g0.1_185_738",
                                                  sequences=["quinoa>wheat"], start_season="kharif-2027",
                                                  irrigation="rainfed", scenario="ssp245"))
    done = run_job(job.job_id, engine.store, WeatherStore(Layout(env["root"]), "tiny"),
                   load_crop_sim(settings.knowledge_dir), P2Config(region=env["region"]))
    assert done.status == "failed" and "no sequence could be simulated" in done.error
    assert run_job("missing", engine.store, None, {}, None) is None


# ---------------------------------------------------------------- /v1/indicators
IND = {"sequence": "soybean>chickpea", "water_score_median": 0.8, "water_score_pessimistic": 0.6, "yield_factor_pessimistic": 0.75}


def test_indicators_route(client, engine, base_request):
    first = client.post("/v1/recommend", json=base_request).json()
    job = client.get(f"/v1/jobs/{first['job_id']}").json()
    ok = client.post("/v1/indicators", json={"cache_key": job["cache_key"], "job_id": job["job_id"], "indicators": [IND]})
    assert ok.status_code == 200 and ok.json() == {"status": "stored", "count": 1}
    assert client.get(f"/v1/jobs/{job['job_id']}").json()["status"] == "done"
    assert engine.store.get_indicators(job["cache_key"])["soybean>chickpea"].water_score_median == 0.8

    assert client.post("/v1/indicators", json={"cache_key": job["cache_key"], "job_id": "nope", "indicators": [IND]}).status_code == 404
    assert client.post("/v1/indicators", json={"cache_key": "other", "job_id": job["job_id"], "indicators": [IND]}).status_code == 422
    assert client.post("/v1/indicators", json={"cache_key": job["cache_key"], "indicators": []}).status_code == 422
    assert client.post("/v1/indicators", json={"cache_key": "k", "indicators": [{**IND, "water_score_median": 3}]}).status_code == 422
    assert client.post("/v1/indicators", json={"cache_key": "k", "indicators": [IND], "extra": 1}).status_code == 422


def test_indicators_route_records_a_failed_run(client, base_request):
    first = client.post("/v1/recommend", json=base_request).json()
    job = client.get(f"/v1/jobs/{first['job_id']}").json()
    r = client.post("/v1/indicators", json={"cache_key": job["cache_key"], "job_id": job["job_id"], "error": "boom"})
    assert r.json() == {"status": "failed_recorded"}
    j = client.get(f"/v1/jobs/{job['job_id']}").json()
    assert j["status"] == "failed" and j["error"] == "boom"


def _bridge(client, seen):
    """An httpx transport that forwards requests to the in-process API, recording them."""
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        r = client.request(request.method, request.url.path, content=request.content, headers=dict(request.headers))
        return httpx.Response(r.status_code, content=r.content, headers={"content-type": "application/json"})
    return HttpClient(transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_publish_via_api_sends_key_and_body(client, base_request):
    first = client.post("/v1/recommend", json=base_request).json()
    job = Job.model_validate(client.get(f"/v1/jobs/{first['job_id']}").json())
    seen = []
    publish_via_api("http://engine/", "s3cret", job, [Indicator(**IND)], http=_bridge(client, seen))
    assert seen[0].url.path == "/v1/indicators" and seen[0].headers["x-api-key"] == "s3cret"
    body = json.loads(seen[0].content)
    assert body["job_id"] == job.job_id and body["cache_key"] == job.cache_key and body["indicators"][0]["sequence"] == IND["sequence"]
    assert client.get(f"/v1/jobs/{job.job_id}").json()["status"] == "done"


# ---------------------------------------------------------------- Vertex-side entry point (run without Vertex)
def test_run_remote_posts_indicators_for_a_job(env, parts, base_request, monkeypatch):
    engine, _, client = parts
    engine.launcher = None                                     # keep the local launcher out of this test
    first = client.post("/v1/recommend", json=base_request).json()
    job = client.get(f"/v1/jobs/{first['job_id']}").json()
    monkeypatch.setenv("FIELDSHIFT_REGIONS_DIR", str(env["regions"]))
    seen = []
    out = run_remote(json.dumps(job), "tiny", env["root"], "v1", "http://engine", http=_bridge(client, seen))
    assert out["indicators"] >= 1 and seen[0].url.path == "/v1/indicators"
    assert client.get(f"/v1/jobs/{job['job_id']}").json()["status"] == "done"
    assert client.post("/v1/recommend", json=base_request).json()["status"] == "refined"


def test_run_remote_reports_errors_back_to_the_engine(env, parts, base_request, monkeypatch):
    engine, _, client = parts
    engine.launcher = None
    first = client.post("/v1/recommend", json=base_request).json()
    job = client.get(f"/v1/jobs/{first['job_id']}").json()
    job["sequences"] = ["quinoa>wheat"]
    monkeypatch.setenv("FIELDSHIFT_REGIONS_DIR", str(env["regions"]))
    with pytest.raises(RuntimeError, match="no sequence could be simulated"):
        run_remote(json.dumps(job), "tiny", env["root"], "v1", "http://engine", http=_bridge(client, []))
    assert client.get(f"/v1/jobs/{job['job_id']}").json()["status"] == "failed"


# ---------------------------------------------------------------- launcher selection
def _settings(settings, **kw):
    return Settings(**{**settings.__dict__, **kw})


def test_build_launcher_choices_and_errors(settings, monkeypatch):
    pipe = load_pipeline_settings()
    store = MemoryStore()
    assert build_launcher(_settings(settings, launcher="none"), pipe, store) is None
    with pytest.raises(ValueError, match="FIELDSHIFT_REGION"):
        build_launcher(_settings(settings, launcher="local"), pipe, store)
    with pytest.raises(ValueError, match="no region file"):
        build_launcher(_settings(settings, launcher="local", region_id="atlantis"), pipe, store)
    assert isinstance(build_launcher(_settings(settings, launcher="local", region_id="pune_demo"), pipe, store), LocalLauncher)
    monkeypatch.delenv("FIELDSHIFT_P2_TEMPLATE", raising=False)
    with pytest.raises(ValueError, match="vertex launcher needs"):
        build_launcher(_settings(settings, launcher="vertex", region_id="pune_demo"), pipe, store)
    with pytest.raises(ValueError, match="unknown launcher"):
        build_launcher(_settings(settings, launcher="cloud", region_id="pune_demo"), pipe, store)


def test_vertex_launcher_uses_the_documented_aiplatform_arguments(monkeypatch):
    from google.cloud import aiplatform
    init_sig = set(inspect.signature(aiplatform.PipelineJob.__init__).parameters)
    submit_sig = set(inspect.signature(aiplatform.PipelineJob.submit).parameters)
    captured = {}

    class FakeJob:
        def __init__(self, **kw):
            captured["init"] = kw

        def submit(self, **kw):
            captured["submit"] = kw

    monkeypatch.setattr(aiplatform, "init", lambda **kw: captured.update(project=kw))
    monkeypatch.setattr(aiplatform, "PipelineJob", FakeJob)
    launcher = VertexLauncher("proj", "asia-south1", "gs://b/p2.json", "gs://b/root", "sa@proj.iam", "https://engine", "gs://b/data", "pune_demo")
    job = Job(cache_key="k", request_id="r", cell_id="c")
    launcher(job)
    assert set(captured["init"]) <= init_sig and set(captured["submit"]) <= submit_sig     # real parameter names
    assert captured["project"] == {"project": "proj", "location": "asia-south1"}
    pv = captured["init"]["parameter_values"]
    assert json.loads(pv["job_json"])["cache_key"] == "k" and pv["region_id"] == "pune_demo" and pv["engine_url"] == "https://engine"
    assert captured["init"]["enable_caching"] is False and captured["submit"] == {"service_account": "sa@proj.iam"}
    assert set(pv) == {"job_json", "region_id", "data_root", "engine_url"}      # matches the P2 pipeline parameters (checked in test_pipelines)
