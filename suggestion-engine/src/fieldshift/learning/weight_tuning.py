"""P4 (later): learning from farmer outcomes.

Deliberately NOT implemented beyond summaries. The implementation plan says nothing is learned
automatically until outcome volume is meaningful, and any tuning method must be agreed with the
agronomists first. What exists: counting what farmers did, and a gate for when tuning may start.
"""
from __future__ import annotations

from collections import Counter

from ..store.models import ActionLog

MIN_OUTCOMES_FOR_TUNING = 100  # placeholder threshold; agree it with the agronomists


def adherence_summary(actions: list[ActionLog]) -> dict:
    ranks = Counter(a.followed_option_rank for a in actions if a.followed_option_rank is not None)
    return {
        "n_actions": len(actions),
        "n_followed_a_recommendation": sum(ranks.values()),
        "n_with_yield": sum(1 for a in actions if a.yield_q_per_acre is not None),
        "followed_by_rank": dict(sorted(ranks.items())),
    }


def ready_for_tuning(actions: list[ActionLog], minimum: int = MIN_OUTCOMES_FOR_TUNING) -> bool:
    return sum(1 for a in actions if a.yield_q_per_acre is not None) >= minimum
