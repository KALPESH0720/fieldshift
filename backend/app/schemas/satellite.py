from datetime import date, datetime

from pydantic import Field, model_validator

from app.schemas.common import PositiveId, StrictSchema


class SatelliteSoilMoistureRequest(StrictSchema):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_range(self):
        from config.settings import settings

        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days + 1 > settings.nasa_smap_max_range_days:
            raise ValueError(f"date range cannot exceed {settings.nasa_smap_max_range_days} days")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        return self


class SatelliteSoilMoistureObservation(StrictSchema):
    date: date
    latitude: float
    longitude: float
    product: str
    product_doi: str
    resolution_km: float = 9
    soil_moisture_am: float | None = Field(default=None, ge=0, le=1)
    soil_moisture_pm: float | None = Field(default=None, ge=0, le=1)
    retrieval_qual_flag_am: int | None = None
    retrieval_qual_flag_pm: int | None = None
    quality_am: str
    quality_pm: str
    unit: str = "m3/m3"


class SatelliteJobResponse(StrictSchema):
    id: PositiveId
    plot_id: PositiveId
    start_date: date
    end_date: date
    status: str
    observation_count: int
    observations: list[SatelliteSoilMoistureObservation]
    error_code: str | None
    created_at: datetime
    updated_at: datetime
