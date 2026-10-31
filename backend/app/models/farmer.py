from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Farmer(Base):
    __tablename__ = "farmers"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120))
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    village: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    plots: Mapped[list["Plot"]] = relationship(back_populates="farmer", cascade="all, delete-orphan", passive_deletes=True)
    alerts: Mapped[list["Alert"]] = relationship(back_populates="farmer", cascade="all, delete-orphan", passive_deletes=True)
