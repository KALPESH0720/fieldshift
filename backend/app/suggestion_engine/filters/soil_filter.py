from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from app.suggestion_engine.filters.base import BaseFilter
if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class SoilFilter(BaseFilter):
    """Apply optional candidate soil-pH bounds when plot soil data is available."""

    def apply(self, candidates: Sequence[Mapping[str, Any]], context: SuggestionContext):
        soil_type = context.soil_type or (context.soil_data or {}).get("soil_type")
        soil_ph = (context.soil_data or {}).get("ph")
        kept = []
        for candidate in candidates:
            minimum = candidate.get("soil_ph_min")
            maximum = candidate.get("soil_ph_max")
            supported_types = candidate.get("suitable_soil_types")
            if soil_type and supported_types and soil_type.casefold() not in {str(item).casefold() for item in supported_types}:
                continue
            if soil_ph is not None and minimum is not None and float(soil_ph) < float(minimum):
                continue
            if soil_ph is not None and maximum is not None and float(soil_ph) > float(maximum):
                continue
            kept.append(candidate)
        return kept
