from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InputDealer(Base):
    """District level seed/input dealer and certification freshness record."""

    __tablename__ = "input_dealers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    district: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(24))
    certification_source: Mapped[str | None] = mapped_column(String(240))
    certification_valid_until: Mapped[date | None] = mapped_column(Date)
    stock_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location = mapped_column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
