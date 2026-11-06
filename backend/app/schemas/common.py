"""Shared strict DTO configuration and common response types."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


PositiveId = Annotated[int, Field(gt=0)]
NonEmptyString = Annotated[str, Field(min_length=1)]


class TimestampedResponse(StrictSchema):
    created_at: datetime
