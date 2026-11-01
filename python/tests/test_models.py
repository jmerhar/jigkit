"""UtcDateTime, the naming convention and the timestamp mixin."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column

from jigkit.db import create_engine, create_sessionmaker, session_scope
from jigkit.models import Base, TimestampMixin, UtcDateTime, utcnow


class Shelf(TimestampMixin, Base):
    """A table for these tests."""

    __tablename__ = "test_models_shelves"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(20))
    checked_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class Book(Base):
    """A table pointing at Shelf, for the foreign key's name."""

    __tablename__ = "test_models_books"

    id: Mapped[int] = mapped_column(primary_key=True)
    shelf_id: Mapped[int] = mapped_column(ForeignKey("test_models_shelves.id"))


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncEngine:
    """A SQLite database holding these tests' tables."""
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'models.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all, tables=[Shelf.__table__, Book.__table__]
        )
    yield engine
    await engine.dispose()


class TestUtcDateTime:
    async def test_an_aware_value_comes_back_aware_and_in_utc(self, engine: AsyncEngine) -> None:
        lisbon_summer = timezone(timedelta(hours=1))
        stored = datetime(2026, 7, 1, 12, 0, tzinfo=lisbon_summer)
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as session:
            session.add(Shelf(id=1, label="a", checked_at=stored))

        async with session_scope(factory) as session:
            loaded = (await session.execute(select(Shelf.checked_at))).scalar_one()

        assert loaded == stored
        assert loaded.tzinfo is UTC
        assert loaded.hour == 11

    async def test_a_naive_value_is_refused(self, engine: AsyncEngine) -> None:
        with pytest.raises(StatementError, match="timezone-aware"):
            async with session_scope(create_sessionmaker(engine)) as session:
                session.add(Shelf(id=1, label="a", checked_at=datetime(2026, 7, 1)))

    async def test_null_stays_null(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as session:
            session.add(Shelf(id=1, label="a"))
        async with session_scope(factory) as session:
            assert (await session.execute(select(Shelf.checked_at))).scalar_one() is None


class TestTimestampMixin:
    async def test_creation_and_update_times_are_maintained(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as session:
            session.add(Shelf(id=1, label="a"))
        async with session_scope(factory) as session:
            shelf = await session.get(Shelf, 1)
            created, first_update = shelf.created_at, shelf.updated_at
            shelf.label = "b"
        async with session_scope(factory) as session:
            shelf = await session.get(Shelf, 1)

        assert created.tzinfo is UTC
        assert shelf.created_at == created
        assert shelf.updated_at > first_update


def test_constraint_names_follow_the_convention() -> None:
    (foreign_key,) = Book.__table__.foreign_key_constraints

    assert Shelf.__table__.primary_key.name == "pk_test_models_shelves"
    assert foreign_key.name == "fk_test_models_books_shelf_id_test_models_shelves"


def test_utcnow_is_aware() -> None:
    assert utcnow().tzinfo is UTC
