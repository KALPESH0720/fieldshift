from datetime import UTC, datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import PositiveId, StrictSchema


class SoilMeasurements(StrictSchema):
    n_val: float | None = Field(default=None, ge=0, le=1_000_000)
    p_val: float | None = Field(default=None, ge=0, le=1_000_000)
    k_val: float | None = Field(default=None, ge=0, le=1_000_000)
    ph: float | None = Field(default=None, ge=0, le=14)
    soil_type: str | None = Field(default=None, max_length=80)
    organic_matter: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def require_measurement(self):
        if not any(getattr(self, key) is not None for key in ("n_val", "p_val", "k_val", "ph", "organic_matter")):
            raise ValueError("Provide at least one measured soil value")
        return self


class SoilTestCreate(SoilMeasurements):
    tested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provenance: Literal["lab", "manual", "imported"] = "manual"
    source_reference: str | None = Field(default=None, max_length=240)
    nutrient_unit: Literal["kg/ha", "mg/kg"] = "kg/ha"
    organic_matter_unit: Literal["percent"] = "percent"

    @model_validator(mode="after")
    def require_timezone(self):
        if self.tested_at.tzinfo is None or self.tested_at.utcoffset() is None:
            raise ValueError("tested_at must include a timezone")
        return self


class SoilTestUpdate(StrictSchema):
    n_val: float | None = Field(default=None, ge=0, le=1_000_000)
    p_val: float | None = Field(default=None, ge=0, le=1_000_000)
    k_val: float | None = Field(default=None, ge=0, le=1_000_000)
    ph: float | None = Field(default=None, ge=0, le=14)
    soil_type: str | None = Field(default=None, max_length=80)
    organic_matter: float | None = Field(default=None, ge=0, le=100)
    tested_at: datetime | None = None
    source_reference: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one soil test field must be supplied")
        if self.tested_at is not None and (self.tested_at.tzinfo is None or self.tested_at.utcoffset() is None):
            raise ValueError("tested_at must include a timezone")
        return self


class SoilTestResponse(StrictSchema):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: PositiveId
    plot_id: PositiveId
    n_val: float | None
    p_val: float | None
    k_val: float | None
    ph: float | None
    soil_type: str | None
    organic_matter: float | None
    nutrient_unit: str
    organic_matter_unit: str
    provenance: str
    source_reference: str | None
    confidence: dict[str, float]
    status: str
    soil_card_upload_id: PositiveId | None
    reviewed_at: datetime | None
    tested_at: datetime


class SoilTestPage(StrictSchema):
    items: list[SoilTestResponse]
    total: int
    limit: int
    offset: int


class SoilCardUploadResponse(StrictSchema):
    id: PositiveId
    plot_id: PositiveId
    status: Literal["queued", "processing", "needs_review", "failed", "approved", "rejected", "expired"]
    content_type: str
    size_bytes: int
    sha256: str
    scan_status: str
    expires_at: datetime
    created_at: datetime
    extracted_metrics: dict[str, float | str | None] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    low_confidence_fields: list[str] = Field(default_factory=list)
    ocr_error_code: str | None = None
    soil_test_id: PositiveId | None = None


class SoilCardReview(SoilMeasurements):
    tested_at: datetime
    nutrient_unit: Literal["kg/ha", "mg/kg"] = "kg/ha"
    organic_matter_unit: Literal["percent"] = "percent"

    @model_validator(mode="after")
    def require_timezone(self):
        if self.tested_at.tzinfo is None or self.tested_at.utcoffset() is None:
            raise ValueError("tested_at must include a timezone")
        return self
