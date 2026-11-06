"""SQLAlchemy declarative base shared by ORM models and migrations."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
