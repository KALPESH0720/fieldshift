from datetime import date, datetime

from sqlalchemy import Date, Numeric, String, DateTime, Index, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (Index(
        "uq_market_price_feed_record", "source", "source_version",
        text("COALESCE(state, '')"), text("COALESCE(district, '')"), "mandi_name", "crop_name", "date",
        text("COALESCE(variety, '')"), text("COALESCE(grade, '')"), unique=True,
    ),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    mandi_name: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    modal_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    district: Mapped[str | None] = mapped_column(String(120), index=True)
    state: Mapped[str | None] = mapped_column(String(120))
    variety: Mapped[str | None] = mapped_column(String(160))
    grade: Mapped[str | None] = mapped_column(String(80))
    min_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    max_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    reported_min_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    reported_max_price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    source: Mapped[str | None] = mapped_column(String(240))
    source_version: Mapped[str | None] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    price_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    reported_unit: Mapped[str | None] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    quality_status: Mapped[str] = mapped_column(String(24), nullable=False, default="verified", server_default="verified")
    mandi_code: Mapped[str | None] = mapped_column(String(80), index=True)
    commodity_code: Mapped[str | None] = mapped_column(String(80), index=True)
    arrivals_quantity: Mapped[float | None] = mapped_column(Numeric(16, 3))
    arrivals_unit: Mapped[str | None] = mapped_column(String(32))


class MinimumSupportPrice(Base):
    __tablename__ = "minimum_support_prices"
    __table_args__ = (UniqueConstraint("crop_name", "season", "year", "source_version", name="uq_msp_crop_season_year_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    season: Mapped[str] = mapped_column(String(80), nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    price_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="INR/quintal")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(240), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
