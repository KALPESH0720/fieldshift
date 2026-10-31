import pytest

from scripts.evaluate_recommendations import evaluate


def test_evaluation_requires_fifty_expert_reviewed_scenarios():
    with pytest.raises(ValueError, match="50 and 100"):
        evaluate({"scenarios": []}, 0.8)


def test_evaluation_reports_top_three_hit_rate():
    scenarios = [
        {"scenario_id": str(index), "approved_by": ["agro-a", "agro-b"],
         "expected_top_crops": ["Ragi"], "actual_top_crops": ["Ragi"]}
        for index in range(50)
    ]
    report = evaluate({"benchmark_version": "test-v1", "scenarios": scenarios}, 0.8)
    assert report["scenario_count"] == 50
    assert report["top3_hit_rate"] == 1.0
    assert report["passed"] is True


def test_evaluation_rejects_scenarios_without_two_distinct_approvals():
    scenarios = [
        {"scenario_id": str(index), "approved_by": ["agro-a", "agro-a"],
         "expected_top_crops": ["Ragi"], "actual_top_crops": ["Ragi"]}
        for index in range(50)
    ]
    with pytest.raises(ValueError, match="two distinct"):
        evaluate({"scenarios": scenarios}, 0.8)
