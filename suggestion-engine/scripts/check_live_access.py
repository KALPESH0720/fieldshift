"""Check access to NASA POWER, NASA Earthdata AppEEARS and Cloud Storage.

    python scripts/check_live_access.py --bucket gs://YOUR_BUCKET
Environment: EARTHDATA_USERNAME, EARTHDATA_PASSWORD (free Earthdata account); Google credentials for the bucket check
(`gcloud auth application-default login`). Use --skip power appeears gcs to leave checks out.
"""
import argparse
import sys

from fieldshift.data.live_check import run_checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket")
    ap.add_argument("--skip", nargs="*", default=[], choices=["power", "appeears", "gcs"])
    args = ap.parse_args()
    results = run_checks(args.bucket, skip=tuple(args.skip))
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
