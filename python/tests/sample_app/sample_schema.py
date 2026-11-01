"""The sample application's models: a parent table and children that point at it.

Covers each column type the synthetic row generator knows, so the migration checks are
exercised against a realistic schema.
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    Enum,
    Float,
    ForeignKey,
    Interval,
    LargeBinary,
    Numeric,
    String,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from jigkit.models import Base, TimestampMixin, UtcDateTime
from jigkit.settings import AppSettings


class Settings(AppSettings):
    """The sample application's settings."""

    database_filename = "sample.db"


class Kind(enum.StrEnum):
    """What a pet is."""

    CAT = "cat"
    DOG = "dog"


class Owner(TimestampMixin, Base):
    """A parent table: pets and notes point at it."""

    __tablename__ = "owners"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(default=True)
    nickname: Mapped[str | None] = mapped_column(String(80))


class Pet(Base):
    """A child whose rows are deleted with their owner."""

    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"))
    kind: Mapped[Kind] = mapped_column(Enum(Kind, native_enum=False))
    born: Mapped[date] = mapped_column(Date)
    fed_at: Mapped[time] = mapped_column(Time)
    seen_at: Mapped[datetime] = mapped_column(UtcDateTime)
    weight: Mapped[float] = mapped_column(Float)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    photo: Mapped[bytes] = mapped_column(LargeBinary)
    traits: Mapped[dict[str, Any]] = mapped_column(JSON)
    tag: Mapped[Any] = mapped_column(Uuid)
    nap: Mapped[timedelta] = mapped_column(Interval)


class Note(Base):
    """A child whose rows lose their owner, rather than disappear, when the owner goes."""

    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("owners.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text)
