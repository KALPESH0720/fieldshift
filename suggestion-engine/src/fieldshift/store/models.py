"""Shared data models.

Two groups: (1) the API contract (request / response) that the backend team consumes, and
(2) domain records exchanged with the data and pipeline side (cell features, indicators,
jobs, alerts, action logs). Group 2 is the interface agreed with Developer B.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SEASON_RE = re.compile(r"^[a-z]+-\d{4}$")
Level = Literal["high", "medium", "low"]
Irrigation = Literal["rainfed", "limited", "full"]
DIMENSIONS = ("soil", "return", "water_risk", "pest")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_season(v: str) -> str:
    if not SEASON_RE.match(v):
        raise ValueError("season must look like 'kharif-2027'")
    return v


# =====================================================================
# 1. API contract: request
# =====================================================================
class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class HistoryItem(BaseModel):
    season: str
    crop: str

    @field_validator("season")
    @classmethod
    def _season(cls, v: str) -> str:
        return _check_season(v)


class Soil(BaseModel):
    texture: Optional[str] = None
    ph: Optional[float] = Field(default=None, ge=0, le=14)
    organic_carbon: Optional[float] = Field(default=None, ge=0)


class Weights(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    soil: float = Field(0.30, ge=0)
    return_: float = Field(0.30, ge=0, alias="return")
    water_risk: float = Field(0.25, ge=0)
    pest: float = Field(0.15, ge=0)

    def as_dict(self) -> dict[str, float]:
        return {"soil": self.soil, "return": self.return_, "water_risk": self.water_risk, "pest": self.pest}


class Preferences(BaseModel):
    weights: Weights = Field(default_factory=Weights)
    flags: list[str] = Field(default_factory=list)


class PriceItem(BaseModel):
    crop: str
    price: float = Field(gt=0)
    unit: str = "INR/quintal"
    source: Literal["msp", "market"] = "market"
    date: Optional[str] = None


class CostItem(BaseModel):
    crop: str
    cost_per_acre: float = Field(ge=0)
    expected_yield_q_per_acre: Optional[float] = Field(default=None, gt=0)


class RecommendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    location: Location
    season: str
    language: str = "en"
    crop_history: list[HistoryItem] = Field(default_factory=list)
    soil: Soil = Field(default_factory=Soil)
    irrigation: Irrigation = "rainfed"
    preferences: Preferences = Field(default_factory=Preferences)
    prices: list[PriceItem] = Field(default_factory=list)
    costs: list[CostItem] = Field(default_factory=list)
    fertilizer_n_price_per_kg: Optional[float] = Field(default=None, ge=0)
    horizon_seasons: Optional[int] = Field(default=None, ge=1, le=3)

    @field_validator("season")
    @classmethod
    def _season(cls, v: str) -> str:
        return _check_season(v)


class RescoreRequest(BaseModel):
    """What-if: re-rank a previous request with new weights/flags. No data is recomputed."""
    model_config = ConfigDict(extra="forbid")
    request_id: str
    weights: Optional[Weights] = None
    flags: Optional[list[str]] = None


# =====================================================================
# 1. API contract: response
# =====================================================================
class ReasonCodeOut(BaseModel):
    code: str
    params: dict[str, Any] = Field(default_factory=dict)
    text_en: Optional[str] = None  # English template for testing; the frontend renders local languages


class ScoreSet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    soil: float
    return_: float = Field(alias="return")
    water_risk: float
    pest: float
    total: float


class Uncertainty(BaseModel):
    pessimistic_total: Optional[float] = None
    top3_stability: Optional[float] = None


class PriceBasis(BaseModel):
    crop: str
    used: Optional[Literal["msp", "market"]] = None
    market: Optional[float] = None
    msp: Optional[float] = None


class Economics(BaseModel):
    net_return_per_acre: Optional[float] = None
    net_return_pessimistic_per_acre: Optional[float] = None
    fertilizer_saved_kg_per_acre: float = 0.0
    fertilizer_saving_inr_per_acre: Optional[float] = None
    price_basis: list[PriceBasis] = Field(default_factory=list)


class Option(BaseModel):
    rank: int
    crop_sequence: list[str]
    seasons: list[str]
    scores: ScoreSet
    uncertainty: Uncertainty
    economics: Economics
    reason_codes: list[ReasonCodeOut]
    trade_off_code: Optional[ReasonCodeOut] = None
    confidence: Level
    sources: list[str]


class Excluded(BaseModel):
    crop: str
    code: str
    params: dict[str, Any] = Field(default_factory=dict)


class Versions(BaseModel):
    model: str
    rules: str
    params: str
    layer: Optional[str] = None


class RecommendResponse(BaseModel):
    request_id: str
    status: Literal["fast", "refined"]
    grid_cell_id: str
    versions: Versions
    options: list[Option]
    excluded_first_season: list[Excluded] = Field(default_factory=list)
    confidence: Level
    needs_human_review: bool
    missing_inputs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    job_id: Optional[str] = None


# =====================================================================
# 2. Domain records shared with Developer B (data / pipelines)
# =====================================================================
class SeasonClimate(BaseModel):
    """Per-cell, per-season climate features written by pipeline P1. Missing values are allowed."""
    rain_mm_median: Optional[float] = None          # season rainfall, median year (POWER)
    rain_mm_dry_year: Optional[float] = None        # season rainfall, dry year (p20)
    stored_water_mm_at_sowing: Optional[float] = None  # SMAP L4 root-zone available water at sowing
    tmean_c: Optional[float] = None                 # season mean temperature
    heat_stress_days: Optional[float] = None
    longest_dry_spell_days: Optional[float] = None


class FutureDelta(BaseModel):
    """Change against the historical baseline for one scenario (NEX-GDDP-CMIP6)."""
    temp_delta_c: Optional[float] = None
    rain_change_pct: Optional[float] = None


class CellFeatures(BaseModel):
    cell_id: str
    layer_version: str
    synthetic: bool = False                         # True for development fixtures
    soil_class: Optional[str] = None
    soil_ph: Optional[float] = None
    soil_organic_carbon: Optional[float] = None
    seasons: dict[str, SeasonClimate] = Field(default_factory=dict)  # keyed by 'kharif', 'rabi', ...
    drought_frequency: Optional[float] = None       # SMAP-based, 0..1
    ndvi_cv: Optional[float] = None
    future: dict[str, FutureDelta] = Field(default_factory=dict)     # keyed by scenario, e.g. 'ssp245'


class Indicator(BaseModel):
    """Simulation output (pipeline P2) for one crop sequence in one cache entry."""
    sequence: str                                   # e.g. 'soybean>wheat'
    water_score_median: float = Field(ge=0, le=1)
    water_score_pessimistic: float = Field(ge=0, le=1)
    yield_factor_pessimistic: float = Field(ge=0, le=1.5)  # dry-year yield relative to median


class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    cache_key: str
    request_id: str
    cell_id: str
    status: Literal["queued", "running", "done", "failed"] = "queued"
    sequences: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class Alert(BaseModel):
    """Written by pipeline P3 (season monitor)."""
    cell_id: str
    crop: Optional[str] = None
    type: str
    severity: Literal["info", "watch", "act"] = "info"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    code: str
    params: dict[str, Any] = Field(default_factory=dict)


class ActionLog(BaseModel):
    """What the farmer actually did. Pseudonymous: no names, phone numbers or exact locations."""
    model_config = ConfigDict(extra="forbid")
    plot_id: str
    cell_id: Optional[str] = None
    request_id: Optional[str] = None
    season: str
    followed_option_rank: Optional[int] = None
    planted_crop: str
    sowing_date: Optional[date] = None
    yield_q_per_acre: Optional[float] = Field(default=None, ge=0)
    cost_per_acre: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None
    logged_at: str = Field(default_factory=utcnow)

    @field_validator("season")
    @classmethod
    def _season(cls, v: str) -> str:
        return _check_season(v)
