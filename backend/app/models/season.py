from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        CheckConstraint("start_month BETWEEN 1 AND 12", name="ck_seasons_start_month"),
        CheckConstraint("end_month BETWEEN 1 AND 12", name="ck_seasons_end_month"),
        UniqueConstraint("district", "year", "season_code", name="uq_seasons_district_year_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    start_month: Mapped[int] = mapped_column(nullable=False)
    end_month: Mapped[int] = mapped_column(nullable=False)
    district: Mapped[str | None] = mapped_column(String(120))
    year: Mapped[int | None] = mapped_column(Integer)
    season_code: Mapped[str | None] = mapped_column(String(24))

    crop_records: Mapped[list["CropRecord"]] = relationship(back_populates="season", passive_deletes=True)
