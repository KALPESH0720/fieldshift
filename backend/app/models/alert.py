from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_alerts_dedupe_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), index=True, nullable=False)
    plot_id: Mapped[int | None] = mapped_column(ForeignKey("plots.id", ondelete="CASCADE"), index=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(240))
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    delivery_receipts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    farmer: Mapped["Farmer"] = relationship(back_populates="alerts")
    plot: Mapped["Plot | None"] = relationship(back_populates="alerts")
