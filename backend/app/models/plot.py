from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy import event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Plot(Base):
    __tablename__ = "plots"
    __table_args__ = (
        CheckConstraint("area_acres > 0", name="ck_plots_area_acres_positive"),
        CheckConstraint("area_value > 0", name="ck_plots_area_value_positive"),
        CheckConstraint("area_unit IN ('acre', 'hectare')", name="ck_plots_area_unit"),
        CheckConstraint(
            "location IS NULL OR (ST_SRID(location) = 4326 AND GeometryType(location) IN ('POINT', 'POLYGON') AND ST_IsValid(location))",
            name="ck_plots_location_valid_wgs84",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    area_acres: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    area_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    area_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="acre", server_default="acre")
    district: Mapped[str | None] = mapped_column(String(120))
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # GEOMETRY accepts both Point and Polygon GeoJSON geometries (WGS 84).
    location = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=True), nullable=True)
    irrigation_type: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    farmer: Mapped["Farmer"] = relationship(back_populates="plots")
    crop_records: Mapped[list["CropRecord"]] = relationship(back_populates="plot", cascade="all, delete-orphan", passive_deletes=True)
    soil_tests: Mapped[list["SoilTest"]] = relationship(back_populates="plot", cascade="all, delete-orphan", passive_deletes=True)
    alerts: Mapped[list["Alert"]] = relationship(back_populates="plot", cascade="all, delete-orphan", passive_deletes=True)


@event.listens_for(Plot, "before_insert")
def _populate_area_value(_mapper, _connection, target: Plot) -> None:
    if target.area_value is None and target.area_acres is not None:
        target.area_value = (
            float(target.area_acres) / 2.4710538147 if target.area_unit == "hectare" else float(target.area_acres)
        )
