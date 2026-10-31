from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.suggestion_engine.pipeline import SuggestionContext


@dataclass(frozen=True)
class ScoreResult:
    """Normalized component score and its user-facing rationale."""

    score: float
    reason: str | None = None
    tradeoff: str | None = None
    metrics: Mapping[str, Any] = field(default_factory=dict)


class BaseScorer(ABC):
    """Scores one crop candidate on a 0–100 scale."""

    key: str = "score"
    weight: float = 1.0

    @abstractmethod
    def score(
        self, candidate: Mapping[str, Any], context: SuggestionContext
    ) -> ScoreResult | float:
        """Return a normalized score or a score with explanation metadata."""
