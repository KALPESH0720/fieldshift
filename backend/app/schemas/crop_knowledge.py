from datetime import datetime
from typing import Literal

from pydantic import Field, HttpUrl

from app.schemas.common import PositiveId, StrictSchema


class CropKnowledgeDataV1(StrictSchema):
    """Typed v1 agronomic/economic assumptions. Drafts may leave evidence incomplete."""

    display_names: dict[str, str] = Field(default_factory=dict)
    varieties: list[str] = Field(default_factory=list)
    expected_yield_kg_per_acre: float | None = Field(default=None, gt=0)
    yield_source: str | None = None
    yield_date: str | None = None
    input_cost_inr_per_acre: float | None = Field(default=None, ge=0)
    cost_source: str | None = None
    cost_date: str | None = None
    cost_currency: str | None = None
    cost_unit: str | None = None
    fertilizer_savings_inr_per_acre: float | None = Field(default=None, ge=0)
    fertilizer_savings_source: str | None = None
    fertilizer_savings_date: str | None = None
    subsidy_eligible: bool | None = None
    eligible_subsidy_inr_per_acre: float | None = Field(default=None, ge=0)
    subsidy_source: str | None = None
    subsidy_checked_date: str | None = None
    soil_ph_min: float | None = Field(default=None, ge=0, le=14)
    soil_ph_max: float | None = Field(default=None, ge=0, le=14)
    suitable_soil_types: list[str] | None = None
    minimum_rainfall_mm: float | None = Field(default=None, ge=0)
    water_requirement_mm: float | None = Field(default=None, gt=0)
    water_requirement_source: str | None = None
    suitable_irrigation_types: list[str] | None = None
    maximum_sowing_delay_days: int | None = Field(default=None, ge=0)
    sowing_alert_enabled: bool = False
    sowing_alert_threshold_days: int | None = Field(default=None, ge=0, le=30)
    minimum_repeat_gap_seasons: int | None = Field(default=1, ge=1, le=10)
    pest_risk_index: float | None = Field(default=None, ge=0, le=100)
    soil_benefit_score: float | None = Field(default=None, ge=0, le=100)
    pest_source: str | None = None
    soil_benefit_source: str | None = None


class CropRuleDraftCreate(StrictSchema):
    crop_name: str = Field(min_length=1, max_length=120)
    rule_version: int = Field(ge=1)
    schema_version: str = Field(default="1.0", min_length=1, max_length=24)
    crop_family: str | None = Field(default=None, max_length=80)
    root_depth: str | None = Field(default=None, max_length=32)
    water_requirement: str | None = Field(default=None, max_length=32)
    nitrogen_effect: float | None = None
    duration_days: int | None = Field(default=None, gt=0)
    suitable_seasons: list[str] | None = None
    suitable_regions: list[str] | None = None
    certified_seed_available: bool | None = None
    source_title: str = Field(min_length=1, max_length=240)
    source_url: str = Field(min_length=8, max_length=2048)
    source_version: str = Field(min_length=1, max_length=120)
    effective_region: str = Field(min_length=1, max_length=120)
    effective_seasons: list[str] = Field(min_length=1)
    knowledge_data: CropKnowledgeDataV1


class CropRuleReviewRequest(StrictSchema):
    decision: Literal["approve", "reject"]
    notes: str | None = None


class CropRuleRollbackRequest(StrictSchema):
    reason: str = Field(min_length=8, max_length=1000)


class CropRuleResponse(StrictSchema):
    id: PositiveId
    crop_name: str
    rule_version: int
    schema_version: str
    source_title: str | None
    source_url: str | None
    source_version: str | None
    effective_region: str | None
    effective_seasons: list[str] | None
    status: str
    approved_at: datetime | None
    activated_at: datetime | None
    knowledge_data: dict | None


class CropRuleAuditResponse(StrictSchema):
    id: PositiveId
    crop_rule_id: PositiveId
    actor_id: str
    action: str
    details: dict
    created_at: datetime
