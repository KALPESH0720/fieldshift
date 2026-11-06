"""Small statistics helpers (pure Python, ignore missing values)."""
from __future__ import annotations

import math
from typing import Iterable, Optional


def _clean(xs: Iterable[Optional[float]]) -> list[float]:
    return [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]


def mean(xs: Iterable[Optional[float]]) -> Optional[float]:
    v = _clean(xs)
    return sum(v) / len(v) if v else None


def percentile(xs: Iterable[Optional[float]], q: float) -> Optional[float]:
    """Linear-interpolation percentile, q in 0..100."""
    if not 0 <= q <= 100:
        raise ValueError("q must be in 0..100")
    v = sorted(_clean(xs))
    if not v:
        return None
    if len(v) == 1:
        return v[0]
    pos = (len(v) - 1) * q / 100.0
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def median(xs: Iterable[Optional[float]]) -> Optional[float]:
    return percentile(xs, 50)


def cv(xs: Iterable[Optional[float]]) -> Optional[float]:
    """Coefficient of variation (population std / mean); None if undefined."""
    v = _clean(xs)
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    if m == 0:
        return None
    var = sum((x - m) ** 2 for x in v) / len(v)
    return math.sqrt(var) / abs(m)
