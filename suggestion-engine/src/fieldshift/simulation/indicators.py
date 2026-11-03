"""Turn per-year simulation results into the Indicator the engine's scoring consumes.

Per year the sequence score is the mean relative yield (water only) over its crops. Across years:
median = typical year; pessimistic = 20th percentile of baseline plus climate-change years pooled;
yield factor = pessimistic / median, i.e. how much a bad year costs relative to a typical one.
"""
from __future__ import annotations

from typing import Optional

from ..common.stats import mean, median, percentile
from ..store.models import Indicator
from .water_balance import SlotResult

YIELD_FACTOR_MAX = 1.5


def yearly_scores(results_by_year: dict[int, list[SlotResult]]) -> dict[int, float]:
    return {y: mean(r.relative_yield for r in slots) for y, slots in results_by_year.items() if slots}


def build_indicator(sequence: str, baseline: dict[int, float], future: Optional[dict[int, float]] = None,
                    min_years: int = 8) -> Optional[Indicator]:
    if len(baseline) < min_years:
        return None
    med = median(baseline.values())
    pool = list(baseline.values()) + list((future or {}).values())
    pess = percentile(pool, 20)
    yf = 1.0 if med <= 0 else min(max(pess / med, 0.0), YIELD_FACTOR_MAX)
    return Indicator(sequence=sequence, water_score_median=round(med, 4),
                     water_score_pessimistic=round(min(pess, 1.0), 4), yield_factor_pessimistic=round(yf, 4))
