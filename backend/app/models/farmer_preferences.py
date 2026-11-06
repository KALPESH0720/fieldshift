from datetime import time

from sqlalchemy import Boolean, ForeignKey, JSON, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FarmerPreferences(Base):
    __tablename__ = "farmer_preferences"

    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), primary_key=True)
    weather_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    quiet_hours_start: Mapped[time | None] = mapped_column(Time)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata", server_default="Asia/Kolkata")
    language: Mapped[str | None] = mapped_column(String(16))
    planned_crops: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
