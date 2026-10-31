from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True, nullable=False)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), index=True, nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scorer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    request_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    rule_snapshot: Mapped[list] = mapped_column(JSON, nullable=False)
    response_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RecommendationOutcome(Base):
    __tablename__ = "recommendation_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendation_runs.id", ondelete="CASCADE"), unique=True, nullable=False)
    planted_crop: Mapped[str] = mapped_column(String(120), nullable=False)
    actual_yield_kg: Mapped[float | None] = mapped_column(Numeric(14, 3))
    actual_input_cost: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR", server_default="INR")
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
