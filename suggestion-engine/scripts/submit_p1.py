"""Submit the compiled P1 pipeline (build/p1.yaml) to Vertex AI.

    python -m pipelines.compile                      # compiles build/p1.yaml and build/p2.yaml
    python scripts/submit_p1.py --region-id pune_demo --layer-version 2026a --source power \
        --soil-source raster --soil-path gs://BUCKET/soil/rasters.json
Needs FIELDSHIFT_GCP_PROJECT, FIELDSHIFT_PIPELINE_ROOT, FIELDSHIFT_DATA_ROOT (gs://...) and optionally
FIELDSHIFT_SERVICE_ACCOUNT. Not run against Google Cloud from the development sandbox.
"""
import argparse
import sys

from fieldshift.common.config import load_pipeline_settings
from fieldshift.common.vertex import submit_pipeline


def build_parameters(a, data_root: str) -> dict:
    """Keys must match the parameters of pipelines/p1_grid_layers/pipeline.py (checked in tests)."""
    return {
        "region_id": a.region_id, "data_root": data_root, "layer_version": a.layer_version, "source": a.source,
        "soil_source": a.soil_source, "soil_path": a.soil_path or "", "smap_csv": a.smap_csv or "",
        "ndvi_csv": a.ndvi_csv or "", "future_json": a.future_json or "", "workers": a.workers,
    }


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="build/p1.yaml")
    ap.add_argument("--region-id", required=True)
    ap.add_argument("--layer-version", required=True)
    ap.add_argument("--source", default="power", choices=["power", "synthetic"])
    ap.add_argument("--soil-source", default="raster", choices=["raster", "csv", "synthetic"])
    ap.add_argument("--soil-path")
    ap.add_argument("--smap-csv")
    ap.add_argument("--ndvi-csv")
    ap.add_argument("--future-json")
    ap.add_argument("--workers", type=int, default=4)
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
    job = submit_pipeline(s.gcp_project, s.gcp_region, a.template, s.pipeline_root, build_parameters(a, s.data_root),
                          display_name=f"fieldshift-p1-{a.region_id}-{a.layer_version}", service_account=s.service_account)
    print("submitted:", getattr(job, "display_name", "p1"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
