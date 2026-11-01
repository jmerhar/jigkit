"""The declarative base every model shares, and the column types that keep data consistent.

One :class:`Base` per process: an application's models and the tables jigkit itself provides
register on the same metadata, so one set of migrations covers them all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

#: Deterministic constraint names. SQLite cannot ALTER a constraint, so Alembic rebuilds the
#: whole table to change one, which it can only do when every constraint has a name it can
#: reproduce.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UtcDateTime(TypeDecorator[datetime]):
    """A timestamp that is always a timezone-aware UTC ``datetime`` in Python.

    SQLite has no timestamp type: it stores a string and hands back a naive ``datetime``, and
    comparing that with ``datetime.now(UTC)`` raises ``TypeError``. Normalising to UTC on the way
    in and re-attaching the zone on the way out keeps every datetime aware, whatever the backend.
    Naive input is rejected rather than assumed to be UTC, because the assumption is wrong exactly
    when a caller has a local time in hand.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:  # noqa: ARG002
        """Store an aware datetime as naive UTC."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"expected a timezone-aware datetime, got {value!r}")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:  # noqa: ARG002
        """Load a stored naive UTC value as an aware datetime."""
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def utcnow() -> datetime:
    """The current time, timezone-aware, for column defaults."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for every model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Creation and modification times, maintained by the ORM."""

    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)
