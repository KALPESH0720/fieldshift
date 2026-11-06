from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


@dataclass(frozen=True)
class RuleDecision:
    allowed: bool = True
    reason: str | None = None
    priority_adjustment: float = 0.0


class BaseRule(ABC):
    """Agronomic decision gate evaluated for each remaining crop candidate."""

    @abstractmethod
    def evaluate(
        self, candidate: Mapping[str, Any], context: SuggestionContext
    ) -> RuleDecision:
        """Return whether the candidate is agronomically acceptable."""
