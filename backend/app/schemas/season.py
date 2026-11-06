from datetime import datetime
from typing import Literal

from pydantic import Field, StringConstraints, model_validator
from typing import Annotated

from app.schemas.common import PositiveId, StrictSchema


class SeasonSeedRequest(StrictSchema):
    district: str = Field(min_length=1, max_length=120)
    year: int = Field(ge=2000, le=2100)


SeasonCode = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{1,23}$")]


class SeasonCreateRequest(SeasonSeedRequest):
    season_code: SeasonCode
    name: str = Field(min_length=1, max_length=80)
    start_month: int = Field(ge=1, le=12)
    end_month: int = Field(ge=1, le=12)


class SeasonUpdateRequest(StrictSchema):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    start_month: int | None = Field(default=None, ge=1, le=12)
    end_month: int | None = Field(default=None, ge=1, le=12)

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one season field must be supplied")
        return self


class SeasonResponse(StrictSchema):
    id: PositiveId
    name: str
    season_code: str | None
    district: str | None
    year: int | None
    start_month: int
    end_month: int


class SeasonSeedResponse(StrictSchema):
    district: str
    year: int
    seasons: list[SeasonResponse]
