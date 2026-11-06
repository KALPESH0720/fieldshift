from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from app.suggestion_engine.filters.base import BaseFilter
if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class CertifiedSeedFilter(BaseFilter):
    """Exclude crops when certified seed is explicitly unavailable."""

    def apply(self, candidates: Sequence[Mapping[str, Any]], context: SuggestionContext):
        return [candidate for candidate in candidates if candidate.get("certified_seed_available") is not False]
