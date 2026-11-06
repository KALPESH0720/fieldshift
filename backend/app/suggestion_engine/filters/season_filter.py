from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from app.suggestion_engine.filters.base import BaseFilter
if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class SeasonFilter(BaseFilter):
    """Keep crops that declare support for the requested season."""

    def apply(self, candidates: Sequence[Mapping[str, Any]], context: SuggestionContext):
        selected = context.season.strip().casefold()
        kept = []
        for candidate in candidates:
            seasons = candidate.get("suitable_seasons", candidate.get("seasons"))
            if seasons is None:
                kept.append(candidate)
                continue
            if isinstance(seasons, str):
                seasons = [part.strip() for part in seasons.split(",")]
            if selected in {str(season).strip().casefold() for season in seasons}:
                kept.append(candidate)
        return kept
