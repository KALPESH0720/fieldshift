from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import PositiveId, StrictSchema


class RecommendationRequest(StrictSchema):
    plot_id: PositiveId
    season: str = Field(min_length=1, max_length=80)
    region: str | None = Field(default=None, min_length=1, max_length=120)
    soil_type: str | None = Field(default=None, min_length=1, max_length=80)
    rainfall_mm: float | None = Field(default=None, ge=0)
    forecast_rainfall_mm: float | None = Field(default=None, ge=0)
    sowing_window_days_remaining: int | None = Field(default=None, ge=0, le=180)
    irrigation_type: str | None = Field(default=None, max_length=40)
    farmer_preferences: list[Literal["low_water", "early_cash", "soil_health", "high_return"]] = Field(default_factory=list, max_length=4)
    available_water_mm: float | None = Field(default=None, ge=0)
    preferred_crops: list[str] = Field(default_factory=list, max_length=100)
    limit: int = Field(default=3, ge=1, le=3, description="MVP policy: return at most the top three options")


class OptionCard(StrictSchema):
    crop_name: str = Field(min_length=1, max_length=120)
    score: float = Field(ge=0, le=100)
    expected_yield_kg: float | None = Field(default=None, ge=0)
    expected_net_return: float | None = None
    return_currency: str = "INR"
    return_unit: str = "per plot per season"
    soil_health_score: float | None = Field(default=None, ge=0, le=100)
    pest_risk_score: float | None = Field(default=None, ge=0, le=100)
    water_risk_score: float | None = Field(default=None, ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    score_components: dict[str, float] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)
    source_citations: list[str] = Field(default_factory=list)
    freshness: dict[str, str | None] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    preference_matches: list[str] = Field(default_factory=list)
    benefit: str
    tradeoff: str


class RecommendationResponse(StrictSchema):
    recommendation_id: PositiveId | None = None
    plot_id: PositiveId
    season: str
    generated_at: datetime
    engine_request_id: str | None = None
    engine_job_id: str | None = None
    engine_status: Literal["fast", "refined"] | None = None
    engine_confidence: Literal["low", "medium", "high"] | None = None
    needs_human_review: bool = False
    missing_inputs: list[str] = Field(default_factory=list)
    excluded_first_season: list[dict] = Field(default_factory=list)
    refinement_url: str | None = None
    ruleset_version: str = "ruleset-v1"
    scorer_version: str = "weighted-v1"
    scoring_weights: dict[str, float] = Field(default_factory=dict)
    options: list[OptionCard] = Field(default_factory=list)
    advisor_referral_required: bool = False
    advisor_referral_reason: str | None = None
    data_quality_notes: list[str] = Field(default_factory=list)


class RecommendationOutcomeCreate(StrictSchema):
    planted_crop: str = Field(min_length=1, max_length=120)
    actual_yield_kg: float | None = Field(default=None, ge=0)
    actual_input_cost: float | None = Field(default=None, ge=0)
    outcome_notes: str | None = None


class SuggestionWeights(StrictSchema):
    soil: float = Field(ge=0)
    return_score: float = Field(alias="return", ge=0)
    water_risk: float = Field(ge=0)
    pest: float = Field(ge=0)

    def engine_dict(self) -> dict[str, float]:
        total = self.soil + self.return_score + self.water_risk + self.pest
        if total <= 0:
            raise ValueError("At least one suggestion weight must be greater than zero")
        return {"soil": self.soil / total, "return": self.return_score / total,
                "water_risk": self.water_risk / total, "pest": self.pest / total}


class RecommendationRescoreCreate(StrictSchema):
    weights: SuggestionWeights | None = None
    flags: list[str] | None = Field(default=None, max_length=32)
