"""Run pipeline P1 on this machine (no Vertex).

    python scripts/run_p1_local.py --region pune_demo --source synthetic --layer-version dev1
    python scripts/run_p1_local.py --region pune_demo --source power --soil-source csv --soil-path soil.csv --layer-version 2026a

`--source synthetic` uses invented weather and soil (development only). The layer is written to
<data-root>/layers/<region>/<layer-version>/cells.json: point FIELDSHIFT_CELLS_PATH at it to run the engine on it.
"""
import argparse
import json
import sys

from fieldshift.common.config import load_pipeline_settings
from fieldshift.features.p1_factory import run_build, run_fetch


def main() -> int:
    s = load_pipeline_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--data-root", default=s.data_root)
    ap.add_argument("--layer-version", required=True)
    ap.add_argument("--source", default="synthetic", choices=["synthetic", "power"])
    ap.add_argument("--soil-source", default="synthetic", choices=["synthetic", "csv", "raster"])
    ap.add_argument("--soil-path")
    ap.add_argument("--smap-csv")
    ap.add_argument("--ndvi-csv")
    ap.add_argument("--future-json")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--refetch", action="store_true")
    a = ap.parse_args()

    failed = run_fetch(a.region, a.data_root, a.source, a.workers, a.refetch)
    print(f"weather: {failed} cells failed to download")
    report = run_build(a.region, a.data_root, a.layer_version, a.source, a.soil_source, a.soil_path,
                       a.smap_csv, a.ndvi_csv, a.future_json)
    print(json.dumps({k: report[k] for k in ("n_cells", "n_with_climate", "n_with_soil", "errors")}, indent=2))
    print(f"{len(report['warnings'])} warnings; layer at {a.data_root}/layers/{a.region}/{a.layer_version}/cells.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
