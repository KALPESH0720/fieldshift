from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PestHostRule(Base):
    """Reviewed crop/host relationships used to explain pest carryover risk."""

    __tablename__ = "pest_host_rules"
    __table_args__ = (UniqueConstraint("target_crop", "effective_region", "season", "version", name="uq_pest_host_rule_scope_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_crop: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    pest_name: Mapped[str] = mapped_column(String(160), nullable=False)
    host_crops: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    host_families: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    effective_region: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    season: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    risk_points: Mapped[float] = mapped_column(nullable=False, default=20)
    source_title: Mapped[str] = mapped_column(String(240), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
