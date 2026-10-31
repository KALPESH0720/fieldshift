from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.common import PositiveId, StrictSchema

Coordinate = Annotated[float, Field(ge=-180, le=180)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
PlotName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
AreaUnit = Literal["acre", "hectare"]
ACRES_PER_HECTARE = 2.4710538147


def to_acres(area_value: float, area_unit: str) -> float:
    return area_value * ACRES_PER_HECTARE if area_unit == "hectare" else area_value


def from_acres(area_acres: float, area_unit: str) -> float:
    return area_acres / ACRES_PER_HECTARE if area_unit == "hectare" else area_acres


class PointGeometry(StrictSchema):
    type: Literal["Point"]
    coordinates: tuple[Coordinate, Latitude]


class PolygonGeometry(StrictSchema):
    type: Literal["Polygon"]
    coordinates: list[list[tuple[Coordinate, Latitude]]] = Field(min_length=1)

    @field_validator("coordinates")
    @classmethod
    def rings_must_be_closed(cls, rings):
        if any(len(ring) < 4 or ring[0] != ring[-1] for ring in rings):
            raise ValueError("Each polygon ring must have at least four positions and be closed")
        return rings


PlotGeometry = PointGeometry | PolygonGeometry


class PlotCreate(StrictSchema):
    name: PlotName
    area_acres: float | None = Field(default=None, gt=0, le=10_000_000)
    area_value: float | None = Field(default=None, gt=0, le=10_000_000)
    area_unit: AreaUnit = "acre"
    district: str | None = Field(default=None, max_length=120)
    location: PlotGeometry | None = None
    irrigation_type: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def resolve_area(self):
        if self.area_acres is None and self.area_value is None:
            raise ValueError("Provide area_value and area_unit, or canonical area_acres")
        converted = to_acres(self.area_value, self.area_unit) if self.area_value is not None else None
        if self.area_acres is None:
            self.area_acres = converted
        elif converted is None:
            self.area_value = from_acres(self.area_acres, self.area_unit)
        elif abs(self.area_acres - converted) > max(0.01, self.area_acres * 0.001):
            raise ValueError("area_acres conflicts with area_value and area_unit")
        if self.area_acres is not None and self.area_acres > 10_000_000:
            raise ValueError("Canonical plot area cannot exceed 10,000,000 acres")
        return self


class PlotUpdate(StrictSchema):
    name: PlotName | None = None
    area_acres: float | None = Field(default=None, gt=0, le=10_000_000)
    area_value: float | None = Field(default=None, gt=0, le=10_000_000)
    area_unit: AreaUnit | None = None
    district: str | None = Field(default=None, max_length=120)
    location: PlotGeometry | None = None
    irrigation_type: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def require_update_value(self):
        if not self.model_fields_set:
            raise ValueError("At least one plot field must be supplied")
        return self


class PlotResponse(PlotCreate):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)

    id: PositiveId
    farmer_id: PositiveId
    area_acres: float
    area_value: float
    area_unit: AreaUnit
    is_archived: bool = False


class PlotListResponse(StrictSchema):
    items: list[PlotResponse]
    total: int
    limit: int
    offset: int


class PlotHistoryItem(StrictSchema):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)

    id: PositiveId
    season_id: PositiveId
    crop_name: str = Field(min_length=1, max_length=120)
    crop_family: str | None = Field(default=None, max_length=80)
    yield_kg: float | None = Field(default=None, ge=0)
    input_costs: float | None = Field(default=None, ge=0)
    outcome_notes: str | None = None
    updated_at: datetime


class PlotHistoryResponse(StrictSchema):
    plot_id: PositiveId
    items: list[PlotHistoryItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class CropHistoryCreate(StrictSchema):
    season_id: PositiveId
    crop_name: str = Field(min_length=1, max_length=120)
    crop_family: str | None = Field(default=None, max_length=80)
    yield_kg: float | None = Field(default=None, ge=0)
    input_costs: float | None = Field(default=None, ge=0)
    outcome_notes: str | None = None


class CropHistoryUpdate(StrictSchema):
    season_id: PositiveId | None = None
    crop_name: str | None = Field(default=None, min_length=1, max_length=120)
    crop_family: str | None = Field(default=None, max_length=80)
    yield_kg: float | None = Field(default=None, ge=0)
    input_costs: float | None = Field(default=None, ge=0)
    outcome_notes: str | None = None

    @model_validator(mode="after")
    def require_update_value(self):
        if not self.model_fields_set:
            raise ValueError("At least one crop history field must be supplied")
        return self
