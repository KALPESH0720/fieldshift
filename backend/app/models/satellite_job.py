from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SatelliteJob(Base):
    """Owner-scoped AppEEARS request and persisted SMAP point time series."""

    __tablename__ = "satellite_jobs"
    __table_args__ = (
        Index("ix_satellite_jobs_farmer_created", "farmer_id", "created_at"),
        Index("ix_satellite_jobs_plot_status", "plot_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", server_default="queued")
    provider_task_id: Mapped[str | None] = mapped_column(String(80))
    observations: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
