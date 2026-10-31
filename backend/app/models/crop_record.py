from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CropRecord(Base):
    __tablename__ = "crop_records"
    __table_args__ = (UniqueConstraint("plot_id", "season_id", "crop_name", name="uq_crop_records_plot_season_crop"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), index=True, nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"), index=True, nullable=False)
    crop_name: Mapped[str] = mapped_column(String(120), nullable=False)
    crop_family: Mapped[str | None] = mapped_column(String(80))
    yield_kg: Mapped[float | None] = mapped_column(Numeric(14, 3))
    input_costs: Mapped[float | None] = mapped_column(Numeric(14, 2))
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    client_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plot: Mapped["Plot"] = relationship(back_populates="crop_records")
    season: Mapped["Season"] = relationship(back_populates="crop_records")
