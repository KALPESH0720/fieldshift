"""Mock of the engine API for the backend team. Returns a canned response so integration can start
before the real engine is deployed.

Run:  uvicorn app:app --port 8001      (from this folder)
Note: the response is the same for every request except request_id. It is NOT a real recommendation.
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

HERE = Path(__file__).parent
EXAMPLE = json.loads((HERE / "example_response.json").read_text(encoding="utf-8"))

app = FastAPI(title="Field Shift engine MOCK")


@app.get("/v1/health")
def health():
    return {"status": "ok", "mock": True}


@app.post("/v1/recommend")
def recommend(body: dict):
    if "location" not in body or "season" not in body:
        raise HTTPException(status_code=422, detail="location and season are required")
    out = dict(EXAMPLE)
    out["request_id"] = body.get("request_id", EXAMPLE["request_id"])
    out["notes"] = list(EXAMPLE.get("notes", [])) + ["MOCK_RESPONSE"]
    return out


@app.get("/v1/jobs/{job_id}")
def job(job_id: str):
    return {"job_id": job_id, "status": "done", "cache_key": "mock", "request_id": "mock",
            "cell_id": EXAMPLE["grid_cell_id"], "sequences": [], "error": None,
            "created_at": "2026-10-31T00:00:00+00:00", "updated_at": "2026-10-31T00:00:00+00:00"}
