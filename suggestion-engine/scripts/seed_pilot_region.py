"""Create a region file from a bounding box, so a new district is one command.

    python scripts/seed_pilot_region.py --id nashik --name "Nashik" --bbox 73.5 19.8 74.2 20.4
The file starts as status 'draft' with the same season windows as the demo region: confirm them with the agronomist.
"""
import argparse
import sys
from pathlib import Path

import yaml

from fieldshift.common.config import REPO_ROOT
from fieldshift.common.region import RegionConfig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    ap.add_argument("--cell-size", type=float, default=0.1)
    ap.add_argument("--years", nargs=2, type=int, default=[2005, 2024])
    ap.add_argument("--crops", nargs="*", default=[])
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "knowledge" / "regions"))
    a = ap.parse_args()
    out = Path(a.out_dir) / f"{a.id}.yaml"
    if out.exists():
        print(f"{out} already exists; not overwriting", file=sys.stderr)
        return 1
    region = RegionConfig.model_validate({
        "id": a.id, "name": a.name, "status": "draft", "bbox": a.bbox, "cell_size_deg": a.cell_size,
        "climate_years": a.years, "crops": a.crops,
        "seasons": {"kharif": {"start": [6, 1], "end": [10, 31]}, "rabi": {"start": [11, 1], "end": [3, 31]}},
    })
    data = region.model_dump(mode="json")
    for s in data["seasons"].values():
        s["start"], s["end"] = list(s["start"]), list(s["end"])
    data["climate_years"] = list(data["climate_years"])
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
