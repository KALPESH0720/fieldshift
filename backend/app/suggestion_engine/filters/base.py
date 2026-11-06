from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


class BaseFilter(ABC):
    """Removes candidates that cannot be recommended in the current context."""

    @abstractmethod
    def apply(
        self, candidates: Sequence[Mapping[str, Any]], context: SuggestionContext
    ) -> list[Mapping[str, Any]]:
        """Return the subset of candidates that passes this filter."""
