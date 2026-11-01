"""The async database engine, its sessions, and the transaction boundary.

SQLite is the default backend and gets the pragmas its schema assumptions depend on; PostgreSQL
(the ``postgres`` extra) gets a pre-ping, so a connection the server dropped is replaced instead
of failing the next request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

#: Milliseconds a SQLite connection waits for a lock before giving up.
SQLITE_BUSY_TIMEOUT_MS = 5000


def is_sqlite(url: str) -> bool:
    """Whether ``url`` names a SQLite database, whose pragmas another backend would reject."""
    return url.startswith("sqlite")


def apply_sqlite_pragmas(dbapi_connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    """Turn on the SQLite behaviour a schema with foreign keys assumes.

    ``foreign_keys`` is off by default in SQLite, which silently makes every ``ON DELETE`` rule a
    no-op. WAL lets background work write while a request reads, instead of the two blocking each
    other, and the busy timeout makes a writer wait for a lock rather than fail at once.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def create_engine(url: str, **kwargs: Any) -> AsyncEngine:
    """Build an async engine for ``url``, with the backend's connection setup wired in.

    Keyword arguments go to SQLAlchemy's ``create_async_engine``.
    """
    if is_sqlite(url):
        engine = create_async_engine(url, **kwargs)
        event.listen(engine.sync_engine, "connect", apply_sqlite_pragmas)
        return engine
    kwargs.setdefault("pool_pre_ping", True)
    return create_async_engine(url, **kwargs)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A session factory that leaves loaded objects usable after a commit.

    ``expire_on_commit=False`` so a handler can read the object it just saved without a second
    round trip, which under async would be implicit IO hidden behind attribute access.
    """
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """A transaction that commits on success and rolls back on any exception.

    Read-only blocks commit too. On PostgreSQL that ends them as a no-op COMMIT instead of a
    ROLLBACK, which keeps the server's rollback ratio meaningful.
    """
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
