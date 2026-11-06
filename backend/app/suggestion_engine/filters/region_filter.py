from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from app.suggestion_engine.filters.base import BaseFilter

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class RegionFilter(BaseFilter):
    """Exclude crops whose declared suitable regions omit the requested region."""

    def apply(self, candidates: Sequence[Mapping[str, Any]], context: SuggestionContext):
        if not context.region:
            return list(candidates)
        selected = context.region.strip().casefold()
        kept = []
        for candidate in candidates:
            regions = candidate.get("suitable_regions", candidate.get("regions"))
            if regions is None:
                kept.append(candidate)
                continue
            if isinstance(regions, str):
                regions = [value.strip() for value in regions.split(",")]
            if selected in {str(region).strip().casefold() for region in regions}:
                kept.append(candidate)
        return kept
