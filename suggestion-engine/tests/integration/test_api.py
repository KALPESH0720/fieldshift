from fastapi.testclient import TestClient

from fieldshift.api.main import create_app
from fieldshift.common.config import Settings
from fieldshift.engine.recommend import Engine
from fieldshift.store.models import Indicator


def test_health(client):
    body = client.get("/v1/health").json()
    assert body["status"] == "ok" and "rules" in body and body["knowledge_reviewed"] is False


def test_recommend_shape_and_aliases(client, base_request):
    r = client.post("/v1/recommend", json=base_request)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "fast" and d["job_id"]
    assert 1 <= len(d["options"]) <= 3
    first = d["options"][0]
    assert set(first["scores"]) == {"soil", "return", "water_risk", "pest", "total"}  # 'return' alias
    assert len(first["crop_sequence"]) == 2 and first["seasons"] == ["kharif-2027", "rabi-2027"]
    assert first["reason_codes"] and first["trade_off_code"]["code"]
    assert 0 <= first["uncertainty"]["top3_stability"] <= 1
    ranks = [o["rank"] for o in d["options"]]
    assert ranks == sorted(ranks)
    totals = [o["scores"]["total"] for o in d["options"]]
    assert totals == sorted(totals, reverse=True)


def test_hard_rules_are_respected_in_every_option(client, base_request):
    d = client.post("/v1/recommend", json=base_request).json()
    for o in d["options"]:
        assert o["crop_sequence"][0] != "maize"  # maize was grown kharif-2026, gap of 2 seasons required


def test_validation_errors(client, base_request):
    assert client.post("/v1/recommend", json={**base_request, "season": "monsoon"}).status_code == 422
    assert client.post("/v1/recommend", json={**base_request, "season": "summer-2027"}).status_code == 422
    assert client.post("/v1/recommend", json={**base_request, "unknown_field": 1}).status_code == 422
    assert client.post("/v1/recommend", json={**base_request, "location": {"lat": 120, "lon": 0}}).status_code == 422


def test_rescore_changes_ranking_inputs_without_new_job(client, base_request):
    first = client.post("/v1/recommend", json={**base_request, "request_id": "r1"}).json()
    r = client.post("/v1/rescore", json={"request_id": "r1", "weights": {"soil": 0.0, "return": 1.0, "water_risk": 0.0, "pest": 0.0}})
    assert r.status_code == 200
    second = r.json()
    assert second["job_id"] == first["job_id"]  # same cache key, no duplicate job
    assert second["options"][0]["scores"]["total"] != first["options"][0]["scores"]["total"]
    assert client.post("/v1/rescore", json={"request_id": "nope"}).status_code == 404


def test_job_is_idempotent_per_cache_key_and_launcher_called_once(kb, store, settings, base_request):
    launched = []
    engine = Engine(kb, store, settings, launcher=launched.append)
    c = TestClient(create_app(engine))
    j1 = c.post("/v1/recommend", json={**base_request, "request_id": "a"}).json()["job_id"]
    j2 = c.post("/v1/recommend", json={**base_request, "request_id": "b"}).json()["job_id"]
    assert j1 == j2 and len(launched) == 1
    job = c.get(f"/v1/jobs/{j1}").json()
    assert job["status"] == "queued" and job["sequences"]
    assert c.get("/v1/jobs/unknown").status_code == 404


def test_cached_indicators_upgrade_the_answer_to_refined(client, engine, base_request):
    first = client.post("/v1/recommend", json=base_request).json()
    job = client.get(f"/v1/jobs/{first['job_id']}").json()
    top_seq = ">".join(first["options"][0]["crop_sequence"])
    engine.store.put_indicators(job["cache_key"], [
        Indicator(sequence=">".join(o["crop_sequence"]), water_score_median=0.6,
                  water_score_pessimistic=0.3, yield_factor_pessimistic=0.5)
        for o in first["options"]
    ])
    second = client.post("/v1/recommend", json=base_request).json()
    assert second["status"] == "refined" and second["job_id"] is None
    assert second["options"][0]["uncertainty"]["pessimistic_total"] < first["options"][0]["uncertainty"]["pessimistic_total"]
    assert top_seq  # sanity


def test_actions_alerts_optimize_and_delete(client, base_request):
    r = client.post("/v1/recommend", json={**base_request, "request_id": "r9"})
    assert r.status_code == 200
    a = {"plot_id": "plot-abc", "request_id": "r9", "season": "kharif-2027", "planted_crop": "soybean",
         "followed_option_rank": 1, "yield_q_per_acre": 5.5}
    assert client.post("/v1/actions", json=a).status_code == 201
    assert client.post("/v1/actions", json={**a, "phone": "123"}).status_code == 422  # no personal data accepted
    assert client.delete("/v1/actions/plot-abc").json() == {"deleted": 1}
    assert client.get("/v1/alerts", params={"lat": 18.52, "lon": 73.85}).json() == []
    assert client.get("/v1/alerts").status_code == 422
    assert client.post("/v1/optimize").status_code == 501


def test_api_key_enforced_when_configured(kb, store, settings, base_request):
    secured = Settings(**{**settings.__dict__, "api_key": "s3cret"})
    c = TestClient(create_app(Engine(kb, store, secured)))
    assert c.post("/v1/recommend", json=base_request).status_code == 401
    assert c.post("/v1/recommend", json=base_request, headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.post("/v1/recommend", json=base_request, headers={"X-API-Key": "s3cret"}).status_code == 200
    assert c.get("/v1/health").status_code == 200
