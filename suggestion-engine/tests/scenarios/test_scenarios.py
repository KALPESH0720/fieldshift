"""Scenario suite: expert-approved cases run in CI on every change to knowledge/ or engine/.

The cases in cases/ are PLACEHOLDERS written by the developer. The agronomist replaces and
extends them (target 50-100 cases) and signs each one off.
"""
from pathlib import Path

import pytest
import yaml

from fieldshift.store.models import RecommendRequest

CASES = sorted((Path(__file__).parent / "cases").glob("*.yaml"))
ORDER = ["low", "medium", "high"]


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_scenario(path, engine):
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    resp = engine.recommend(RecommendRequest.model_validate(case["request"]))
    expect = case["expect"]

    excluded = {e.crop for e in resp.excluded_first_season}
    for crop in expect.get("excluded_includes", []):
        assert crop in excluded, f"{crop} should be excluded; excluded={sorted(excluded)}"
    for crop in expect.get("first_crop_never", []):
        assert all(o.crop_sequence[0] != crop for o in resp.options), f"{crop} must not be recommended first"
    if "confidence_at_most" in expect:
        assert ORDER.index(resp.confidence) <= ORDER.index(expect["confidence_at_most"])
    if "needs_human_review" in expect:
        assert resp.needs_human_review is expect["needs_human_review"]
    for m in expect.get("missing_includes", []):
        assert m in resp.missing_inputs
    for n in expect.get("notes_include", []):
        assert n in resp.notes
    if "any_option_reason" in expect:
        found = {rc.code for o in resp.options for rc in o.reason_codes}
        assert expect["any_option_reason"] in found, f"reasons seen: {sorted(found)}"
    assert len(resp.options) >= expect.get("min_options", 0)
