"""Compile pipelines to spec files Vertex can run.

    python -m pipelines.compile                 -> build/p1.yaml, build/p2.yaml
    python -m pipelines.compile --out somewhere

Set FIELDSHIFT_BASE_IMAGE to the pushed image first, otherwise components point at a stock Python image
that does not contain fieldshift. Submitting to Vertex is done by the launcher (P2) or by hand (P1);
see docs/runbook.md. Not run against Google Cloud from the development sandbox.
"""
from __future__ import annotations

import argparse
import os

from pipelines.p1_grid_layers.pipeline import compile_pipeline as compile_p1
from pipelines.p2_simulation.pipeline import compile_pipeline as compile_p2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for name, fn in (("p1.yaml", compile_p1), ("p2.yaml", compile_p2)):
        print("wrote", fn(os.path.join(args.out, name)))


if __name__ == "__main__":
    main()
