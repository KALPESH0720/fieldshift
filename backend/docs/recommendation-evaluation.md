# Recommendation benchmark gate

The project PDF calls for an expert-approved offline evaluation set and calibration reporting. No expert labels or agreed pass threshold are present in the repository, so do not manufacture them or report a passing benchmark.

Create a reviewed JSON benchmark based on [`../data/evaluation/benchmark-template.json`](../data/evaluation/benchmark-template.json), with 50–100 scenarios. Each scenario should preserve a stable ID, versioned request and rule/scorer versions, at least two distinct agronomist IDs in `approved_by`, a set of acceptable crop names in `expected_top_crops`, and the produced top-three crop names in `actual_top_crops`. Keep private farmer data out of the benchmark; use synthetic or consented/de-identified inputs. Record reviewer date/source and confidence notes in each scenario when curating the first dataset.

Run the evaluator with the threshold approved by the project/agronomy owners:

```sh
python scripts/evaluate_recommendations.py data/evaluation/mysuru-v1.json --min-top3-hit-rate 0.80 --report reports/recommendations-mysuru-v1.json
```

Use the same command in PowerShell. The example threshold is illustrative only; it is not an agreed release threshold. The evaluator refuses fewer than 50 or more than 100 scenarios, scenarios lacking two distinct approvals, or empty labels/results. It reports top-three hit rate and exit status. Before calling the benchmark a calibration report, add agreed calibration metrics and thresholds for confidence/outcomes; top-three hit rate alone measures ranking coverage, not probability calibration.

The current pilot seed is deliberately draft-only. UAS Bengaluru's Mysuru district agro-advisory dated 17 October 2025 and UASB's agroclimatic zone overview support the pilot's regional/source metadata; they do not provide the complete yield, cost, pest, water, or subsidy assumptions needed for active advice. An agronomist panel must provide and approve those values before activation.
