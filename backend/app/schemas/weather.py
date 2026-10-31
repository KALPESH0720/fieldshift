from datetime import datetime, time
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.common import PositiveId, StrictSchema


class WeatherForecastPoint(StrictSchema):
    at: datetime
    rainfall_mm: float | None = Field(default=None, ge=0)
    temperature_c: float | None = Field(default=None, ge=-90, le=65)
    wind_speed_m_s: float | None = Field(default=None, ge=0, le=150)
    sowing_window_days_remaining_by_crop: dict[str, int] = Field(default_factory=dict)


class WeatherForecastResponse(StrictSchema):
    plot_id: PositiveId
    provider: str
    latitude: float
    longitude: float
    location_key: str
    units: dict[str, str]
    fetched_at: datetime
    expires_at: datetime
    current: WeatherForecastPoint | None = None
    forecast: list[WeatherForecastPoint]
    hourly: list[dict] = Field(default_factory=list)
    daily: list[dict] = Field(default_factory=list)
    variable_units: dict[str, dict[str, str]] = Field(default_factory=dict)
    attribution: str = "Weather data by Open-Meteo.com"
    attribution_url: str = "https://open-meteo.com/"
    cached: bool = False


class WeatherSnapshotHistoryItem(StrictSchema):
    id: PositiveId
    plot_id: PositiveId
    provider: str
    location_key: str
    latitude: float
    longitude: float
    units: dict[str, str]
    forecast: dict
    status: Literal["available", "failed"]
    error_code: str | None = None
    fetched_at: datetime
    expires_at: datetime


class FarmerNotificationPreferences(StrictSchema):
    weather_alerts_enabled: bool = False
    reminders_enabled: bool = False
    sms_enabled: bool = False
    whatsapp_enabled: bool = False
    quiet_hours_start: time | None = None
    quiet_hours_end: time | None = None
    timezone: str = "Asia/Kolkata"
    language: Literal["en", "hi", "kn"] | None = None
    planned_crops: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_preferences(self):
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError("Set both quiet-hours boundaries or leave both unset")
        if self.quiet_hours_start == self.quiet_hours_end and self.quiet_hours_start is not None:
            raise ValueError("Quiet hours must have different start and end times")
        if any(not name.strip() for name in self.planned_crops):
            raise ValueError("planned_crops cannot contain empty names")
        return self


class FarmerNotificationPreferencesResponse(FarmerNotificationPreferences):
    farmer_id: PositiveId


class AlertResponse(StrictSchema):
    id: PositiveId
    plot_id: PositiveId | None
    alert_type: str
    status: str
    payload: dict
    attempt_count: int
    next_attempt_at: datetime | None
    last_error_code: str | None
    delivery_receipts: dict
    created_at: datetime
    dead_lettered_at: datetime | None


class WeatherUnits(StrictSchema):
    rainfall: Literal["mm", "in"] | None = None
    temperature: Literal["C", "F"] | None = None
    wind_speed: Literal["m/s", "km/h"] | None = None
