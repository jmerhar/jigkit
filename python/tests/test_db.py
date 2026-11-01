"""The engine's backend setup and the transaction boundary."""

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from jigkit.db import create_engine, create_sessionmaker, is_sqlite, session_scope


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncEngine:
    """A SQLite engine on a throwaway file, with one table."""
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE items (name TEXT)"))
    yield engine
    await engine.dispose()


async def _count(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        return (await connection.execute(text("SELECT count(*) FROM items"))).scalar_one()


class TestEngine:
    async def test_sqlite_connections_get_the_pragmas(self, engine: AsyncEngine) -> None:
        async with engine.connect() as connection:
            foreign_keys = (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one()
            journal = (await connection.execute(text("PRAGMA journal_mode"))).scalar_one()
            timeout = (await connection.execute(text("PRAGMA busy_timeout"))).scalar_one()

        assert (foreign_keys, journal, timeout) == (1, "wal", 5000)

    async def test_other_backends_pre_ping_their_connections(self) -> None:
        # Building the engine opens no connection, so no server is needed.
        engine = create_engine("postgresql+asyncpg://user@localhost/app")
        try:
            assert engine.pool._pre_ping is True
        finally:
            await engine.dispose()

    async def test_an_explicit_pre_ping_setting_is_kept(self) -> None:
        engine = create_engine("postgresql+asyncpg://user@localhost/app", pool_pre_ping=False)
        try:
            assert engine.pool._pre_ping is False
        finally:
            await engine.dispose()

    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("sqlite+aiosqlite:///x.db", True),
            ("sqlite:///x.db", True),
            ("postgresql+asyncpg://h/d", False),
        ],
    )
    def test_is_sqlite(self, url: str, expected: bool) -> None:
        assert is_sqlite(url) is expected


class TestSessionScope:
    async def test_commits_on_success(self, engine: AsyncEngine) -> None:
        async with session_scope(create_sessionmaker(engine)) as session:
            await session.execute(text("INSERT INTO items VALUES ('kept')"))

        assert await _count(engine) == 1

    async def test_rolls_back_on_an_exception(self, engine: AsyncEngine) -> None:
        with pytest.raises(ValueError):
            async with session_scope(create_sessionmaker(engine)) as session:
                await session.execute(text("INSERT INTO items VALUES ('lost')"))
                raise ValueError("boom")

        assert await _count(engine) == 0

    async def test_rolls_back_on_cancellation(self, engine: AsyncEngine) -> None:
        # CancelledError is a BaseException, not an Exception, and a cancelled request must not
        # leave half its writes behind.
        with pytest.raises(asyncio.CancelledError):
            async with session_scope(create_sessionmaker(engine)) as session:
                await session.execute(text("INSERT INTO items VALUES ('lost')"))
                raise asyncio.CancelledError

        assert await _count(engine) == 0

    async def test_objects_stay_readable_after_the_commit(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)

        assert factory.kw["expire_on_commit"] is False
        assert factory.kw["autoflush"] is False
