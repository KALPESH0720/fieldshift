from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SoilTest(Base):
    __tablename__ = "soil_tests"
    __table_args__ = (
        CheckConstraint("n_val IS NULL OR n_val >= 0", name="ck_soil_tests_n_nonnegative"),
        CheckConstraint("p_val IS NULL OR p_val >= 0", name="ck_soil_tests_p_nonnegative"),
        CheckConstraint("k_val IS NULL OR k_val >= 0", name="ck_soil_tests_k_nonnegative"),
        CheckConstraint("ph IS NULL OR ph BETWEEN 0 AND 14", name="ck_soil_tests_ph_range"),
        CheckConstraint("organic_matter IS NULL OR organic_matter BETWEEN 0 AND 100", name="ck_soil_tests_organic_matter_range"),
        UniqueConstraint("soil_card_upload_id", name="uq_soil_tests_soil_card_upload_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), index=True, nullable=False)
    n_val: Mapped[float | None] = mapped_column(Numeric(10, 3))
    p_val: Mapped[float | None] = mapped_column(Numeric(10, 3))
    k_val: Mapped[float | None] = mapped_column(Numeric(10, 3))
    ph: Mapped[float | None] = mapped_column(Numeric(4, 2))
    soil_type: Mapped[str | None] = mapped_column(String(80))
    organic_matter: Mapped[float | None] = mapped_column(Numeric(8, 3))
    nutrient_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="kg/ha", server_default="kg/ha")
    organic_matter_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="percent", server_default="percent")
    card_photo_url: Mapped[str | None] = mapped_column(String(2048))
    provenance: Mapped[str] = mapped_column(String(32), nullable=False, default="legacy", server_default="legacy")
    source_reference: Mapped[str | None] = mapped_column(String(240))
    confidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="approved", server_default="approved")
    reviewed_by_farmer_id: Mapped[int | None] = mapped_column(ForeignKey("farmers.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    soil_card_upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("soil_card_uploads.id", ondelete="SET NULL"),
    )
    tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    plot: Mapped["Plot"] = relationship(back_populates="soil_tests")
