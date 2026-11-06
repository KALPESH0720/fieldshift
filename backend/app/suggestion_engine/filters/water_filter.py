from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from app.suggestion_engine.filters.base import BaseFilter
if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class WaterFilter(BaseFilter):
    """Exclude crops whose stated water requirement exceeds plot availability."""

    def apply(self, candidates: Sequence[Mapping[str, Any]], context: SuggestionContext):
        kept = []
        for candidate in candidates:
            required = candidate.get("water_requirement_mm", candidate.get("water_required_mm"))
            # Categorical water_requirement is used by some crop catalogs; compare only
            # numeric measurements so unknown units never cause an accidental rejection.
            if (context.available_water_mm is not None and isinstance(required, (int, float))
                    and required > context.available_water_mm):
                continue
            rainfall_min = candidate.get("minimum_rainfall_mm")
            if (rainfall_min is not None and context.forecast_rainfall_mm is not None
                    and context.rainfall_mm is not None
                    and context.rainfall_mm + context.forecast_rainfall_mm < float(rainfall_min)):
                continue
            supported_irrigation = candidate.get("suitable_irrigation_types")
            if (context.irrigation_type and supported_irrigation
                    and context.irrigation_type.casefold() not in {str(item).casefold() for item in supported_irrigation}):
                continue
            kept.append(candidate)
        return kept
