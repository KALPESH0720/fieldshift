"""Validate an expert-reviewed top-three recommendation benchmark."""

import argparse
import json
from pathlib import Path
from statistics import mean


def evaluate(payload: dict, minimum_top3_hit_rate: float) -> dict:
    scenarios = payload.get("scenarios", [])
    if not 50 <= len(scenarios) <= 100:
        raise ValueError("benchmark must contain between 50 and 100 scenarios")
    hits = []
    for scenario in scenarios:
        reviewers = set(scenario.get("approved_by", []))
        if len(reviewers) < 2:
            raise ValueError(f"scenario {scenario.get('scenario_id')} needs two distinct expert approvals")
        expected = {str(name).casefold() for name in scenario.get("expected_top_crops", [])}
        actual = [str(name).casefold() for name in scenario.get("actual_top_crops", [])[:3]]
        if not expected or not actual:
            raise ValueError(f"scenario {scenario.get('scenario_id')} needs expected and actual crop lists")
        hits.append(any(name in expected for name in actual))
    hit_rate = mean(hits)
    return {
        "benchmark_version": payload.get("benchmark_version", "unspecified"),
        "scenario_count": len(scenarios),
        "top3_hit_rate": round(hit_rate, 4),
        "minimum_top3_hit_rate": minimum_top3_hit_rate,
        "passed": hit_rate >= minimum_top3_hit_rate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--min-top3-hit-rate", type=float, required=True,
                        help="expert-agreed threshold in [0,1]; never inferred by this tool")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not 0 <= args.min_top3_hit_rate <= 1:
        parser.error("--min-top3-hit-rate must be between 0 and 1")
    try:
        result = evaluate(json.loads(args.benchmark.read_text(encoding="utf-8")), args.min_top3_hit_rate)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    report = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
