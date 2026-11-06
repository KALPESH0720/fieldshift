from datetime import datetime

from pydantic import ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated

from app.schemas.auth import PhoneNumber
from app.schemas.common import PositiveId, StrictSchema


FarmerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class FarmerCreate(StrictSchema):
    name: FarmerName
    language: str = Field(default="en", min_length=2, max_length=16)
    village: str | None = Field(default=None, max_length=120)


class FarmerUpdate(StrictSchema):
    name: FarmerName | None = None
    language: str | None = Field(default=None, min_length=2, max_length=16)
    village: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def require_fields(self):
        if not self.model_fields_set:
            raise ValueError("At least one farmer field must be supplied")
        return self


class FarmerResponse(StrictSchema):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, from_attributes=True)

    id: PositiveId
    phone: PhoneNumber
    name: str | None
    language: str
    village: str | None
    created_at: datetime
