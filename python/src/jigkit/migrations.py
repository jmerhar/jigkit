"""Alembic's environment, shared: the whole body of an application's ``alembic/env.py``.

An application's env.py becomes::

    from jigkit.migrations import run_migrations

    from myapp.config import get_settings
    from myapp.models import Base

    run_migrations(get_settings().resolved_database_url, Base.metadata)

Migrations run through jigkit's own engine, so ``alembic upgrade head`` and the running
application can never disagree about which database is meant or how it is connected to.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from alembic import context
from sqlalchemy import Connection, MetaData, event
from sqlalchemy.engine import make_url

from .db import create_engine, is_sqlite
from .models import UtcDateTime


def render_item(obj_type: str, obj: object, autogen_context: Any) -> str | bool:  # noqa: ARG001
    """Render :class:`~jigkit.models.UtcDateTime` as the plain ``DateTime`` it is built on.

    A migration has to keep running years later, and one that imports an application class stops
    working when that class moves. At the DDL level the type is exactly ``sa.DateTime()``.

    Everything else returns False, Alembic's "use the default rendering"; None would render the
    item as an empty string.
    """
    if obj_type == "type" and isinstance(obj, UtcDateTime):
        return "sa.DateTime()"
    return False


def run_migrations(url: str, metadata: MetaData) -> None:
    """Run the migrations Alembic was asked for against the database at ``url``.

    Online, this applies them; offline (``alembic upgrade --sql``), it prints the SQL instead.
    The logging configuration in alembic.ini is applied first, as Alembic's own template does.
    """
    if context.config.config_file_name is not None:
        fileConfig(context.config.config_file_name)
    if context.is_offline_mode():
        _run_offline(url, metadata)
    else:
        asyncio.run(_run_online(url, metadata))


def _configure_options(metadata: MetaData) -> dict[str, Any]:
    """The Alembic options both modes share.

    ``render_as_batch`` is required for SQLite, which cannot ALTER a column or a constraint:
    batch mode copies the table instead. Set unconditionally, it keeps generated migrations
    portable between backends.
    """
    return {
        "target_metadata": metadata,
        "render_as_batch": True,
        "compare_type": True,
        "render_item": render_item,
    }


def _run_offline(url: str, metadata: MetaData) -> None:
    """Emit the migrations' SQL to stdout instead of running it."""
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_options(metadata),
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection, metadata: MetaData) -> None:
    """Apply migrations on a live connection, then prove they left no dangling references."""
    context.configure(connection=connection, **_configure_options(metadata))
    with context.begin_transaction():
        context.run_migrations()
    if connection.dialect.name == "sqlite":
        dangling = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if dangling:
            raise RuntimeError(f"the migrations left rows pointing at nothing: {dangling}")


def _without_foreign_keys(dbapi_connection: Any, _record: object) -> None:
    """Turn SQLite's foreign keys off for the migrations.

    Batch mode rebuilds a table by copying it, dropping the original and renaming the copy. With
    foreign keys on, dropping the original runs every ON DELETE rule that points at it, so
    rebuilding a parent table would delete or orphan every child row. The check after the
    migrations stands in for the enforcement left off during them.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=OFF")
    finally:
        cursor.close()


def _ensure_sqlite_directory(url: str) -> None:
    """Create the directory a SQLite file lives in, which SQLite will not do itself."""
    database = make_url(url).database
    if database and database != ":memory:" and not database.startswith("file:"):
        Path(database).parent.mkdir(parents=True, exist_ok=True)


async def _run_online(url: str, metadata: MetaData) -> None:
    """Apply migrations against the database at ``url``."""
    engine = create_engine(url)
    if is_sqlite(url):
        _ensure_sqlite_directory(url)
        # Registered after create_engine's own listener, which turns foreign keys on for every
        # connection, so this one runs last and wins.
        event.listen(engine.sync_engine, "connect", _without_foreign_keys)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run, metadata)
    finally:
        await engine.dispose()
