from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from app.suggestion_engine.filters.base import BaseFilter

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class SowingWindowFilter(BaseFilter):
    def apply(self, candidates: Sequence[Mapping[str, Any]], context: SuggestionContext):
        remaining = context.sowing_window_days_remaining
        if remaining is None:
            return list(candidates)
        return [candidate for candidate in candidates
                if candidate.get("maximum_sowing_delay_days") is None
                or remaining <= int(candidate["maximum_sowing_delay_days"])]

