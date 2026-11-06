"""Compare a current observation with its own history at the same time of year."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

MIN_HISTORY = 8
Level = Literal["ok", "watch", "act"]


@dataclass(frozen=True)
class Anomaly:
    value: float
    median: float
    percentile: float   # share of historical values below the current one (ties count half), 0..100
    level: Level


def percentile_rank(value: float, history: list[float]) -> float:
    below = sum(1 for h in history if h < value)
    ties = sum(1 for h in history if h == value)
    return 100.0 * (below + 0.5 * ties) / len(history)


def classify_low(value: float, history: list[float], watch_pct: float = 20.0, act_pct: float = 10.0) -> Optional[Anomaly]:
    """Unusually LOW values are bad (soil moisture, vegetation). None when the history is too short."""
    if len(history) < MIN_HISTORY:
        return None
    pct = percentile_rank(value, history)
    s = sorted(history)
    med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
    level: Level = "act" if pct <= act_pct else "watch" if pct <= watch_pct else "ok"
    return Anomaly(value, med, round(pct, 1), level)
