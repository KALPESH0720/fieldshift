from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CropRule(Base):
    __tablename__ = "crop_rules"
    __table_args__ = (UniqueConstraint("crop_name", "effective_region", "rule_version", name="uq_crop_rules_region_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_name: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_version: Mapped[str] = mapped_column(String(24), nullable=False, default="1.0")
    source_title: Mapped[str | None] = mapped_column(String(240))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    source_version: Mapped[str | None] = mapped_column(String(120))
    effective_region: Mapped[str | None] = mapped_column(String(120))
    effective_seasons: Mapped[list[str] | None] = mapped_column(JSON)
    knowledge_data: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", server_default="draft")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    crop_family: Mapped[str | None] = mapped_column(String(80), index=True)
    root_depth: Mapped[str | None] = mapped_column(String(32))
    water_requirement: Mapped[str | None] = mapped_column(String(32))
    nitrogen_effect: Mapped[float | None] = mapped_column(Numeric(8, 3))
    duration_days: Mapped[int | None] = mapped_column(Integer)
    suitable_seasons: Mapped[list[str] | None] = mapped_column(JSON)
    suitable_regions: Mapped[list[str] | None] = mapped_column(JSON)
    certified_seed_available: Mapped[bool | None] = mapped_column(Boolean)


class CropRuleReview(Base):
    __tablename__ = "crop_rule_reviews"
    __table_args__ = (UniqueConstraint("crop_rule_id", "reviewer_id", name="uq_crop_rule_reviews_reviewer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_rule_id: Mapped[int] = mapped_column(ForeignKey("crop_rules.id", ondelete="CASCADE"), index=True, nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CropRuleAudit(Base):
    __tablename__ = "crop_rule_audits"

    id: Mapped[int] = mapped_column(primary_key=True)
    crop_rule_id: Mapped[int] = mapped_column(ForeignKey("crop_rules.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
