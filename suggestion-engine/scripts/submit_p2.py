"""Submit the compiled P2 pipeline (build/p2.yaml) to Vertex AI for testing/simulation.

    python -m pipelines.compile                      # compiles build/p1.yaml and build/p2.yaml
    python scripts/submit_p2.py --region-id pune_demo --job-file sample_job.json

Needs FIELDSHIFT_GCP_PROJECT, FIELDSHIFT_PIPELINE_ROOT, FIELDSHIFT_DATA_ROOT (gs://...) and optionally
FIELDSHIFT_SERVICE_ACCOUNT and FIELDSHIFT_ENGINE_URL.
"""
import argparse
import json
import sys

from fieldshift.common.config import load_pipeline_settings
from fieldshift.common.vertex import submit_pipeline


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="build/p2.yaml")
    ap.add_argument("--region-id", default="pune_demo")
    ap.add_argument("--layer-version", default="2026a")
    ap.add_argument("--job-file", help="Path to JSON file containing Job model dump")
    ap.add_argument("--job-json", help="Raw JSON string containing Job model dump")
    ap.add_argument("--engine-url")
    return ap


def main() -> int:
    a = parser().parse_args()
    s = load_pipeline_settings()
    missing = [n for n, v in {"FIELDSHIFT_GCP_PROJECT": s.gcp_project, "FIELDSHIFT_PIPELINE_ROOT": s.pipeline_root}.items() if not v]
    if missing:
        print("missing environment variables:", ", ".join(missing), file=sys.stderr)
        return 1
    if not s.data_root.startswith("gs://"):
        print("FIELDSHIFT_DATA_ROOT must be a gs:// path for Vertex runs", file=sys.stderr)
        return 1

    job_json = a.job_json
    if not job_json and a.job_file:
        with open(a.job_file, "r", encoding="utf-8") as f:
            job_json = f.read()
    if not job_json:
        # Default minimal test job payload
        job_json = json.dumps({
            "cache_key": "test_key",
            "request_id": "test_req",
            "cell_id": "test_cell",
            "shortlist": [],
        })

    engine_url = a.engine_url or s.engine_url or "http://localhost:8080"

    params = {
        "job_json": job_json,
        "region_id": a.region_id,
        "data_root": s.data_root,
        "layer_version": a.layer_version,
        "engine_url": engine_url,
    }

    job = submit_pipeline(
        s.gcp_project, s.gcp_region, a.template, s.pipeline_root, params,
        display_name=f"fieldshift-p2-{a.region_id}", service_account=s.service_account,
    )
    print("submitted P2:", getattr(job, "display_name", "p2"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

