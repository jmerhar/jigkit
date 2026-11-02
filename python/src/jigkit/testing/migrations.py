"""Checks an application runs against its own Alembic migrations.

Every check runs ``alembic`` in a subprocess from the application's directory, exactly as a
container's entrypoint does, so the application's real env.py and settings are what is tested::

    from jigkit.testing.migrations import MigrationProject

    PROJECT = MigrationProject(Path(__file__).parents[1], database_filename="myapp.db")

    def test_models_match_migrations(data_dir):
        PROJECT.assert_models_match(Base.metadata, data_dir)

    def test_one_head():
        PROJECT.assert_single_head()

    def test_rebuilding_parents_keeps_children(data_dir, tmp_path):
        PROJECT.assert_parent_rebuilds_keep_children(Base.metadata, data_dir, tmp_path)

The application's tests build their schema with ``create_all``, so without these nothing would
notice a model change that never got a migration, or a migration that empties a table.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    Interval,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Table,
    Time,
    Uuid,
    create_engine,
    func,
    select,
)

from jigkit.models import UtcDateTime

#: Environment variables passed through to the Alembic subprocess. Everything else is left out,
#: so a developer's own DATABASE_URL or similar cannot point the check at a real database.
PASSED_THROUGH = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT")

#: The revision of the throwaway migration that rebuilds every parent table.
REBUILD_REVISION = "jigkit_rebuild_parents"


class UnsupportedColumnError(TypeError):
    """A column needs a value the synthetic row generator cannot invent."""


@dataclass(frozen=True)
class MigrationProject:
    """An application directory holding ``alembic.ini``, and how to point it at a database.

    ``env`` is added to the subprocess environment, for settings the application insists on
    (a secret key, say). The data directory reaches the application as ``data_dir_variable``.
    """

    directory: Path
    database_filename: str = "app.db"
    env: Mapping[str, str] = field(default_factory=dict)
    data_dir_variable: str = "DATA_DIR"
    ini_name: str = "alembic.ini"

    def config(self) -> Config:
        """The application's Alembic configuration, with paths made absolute."""
        config = Config(str(self.directory / self.ini_name))
        location = config.get_main_option("script_location") or "alembic"
        config.set_main_option("script_location", str(self.directory / location))
        return config

    def sync_url(self, data_dir: Path) -> str:
        """A synchronous URL for the SQLite database the application keeps in ``data_dir``."""
        return f"sqlite:///{data_dir / self.database_filename}"

    def alembic(self, data_dir: Path, *args: str, directory: Path | None = None) -> None:
        """Run ``alembic *args`` against the database in ``data_dir``; raise if it fails.

        ``directory`` runs it from a copy of the project instead of the project itself.
        """
        cwd = directory or self.directory
        environment = {k: v for k, v in os.environ.items() if k in PASSED_THROUGH}
        # Coverage measures subprocesses through variables of its own; keep them so the code
        # the migrations run is measured too.
        environment |= {k: v for k, v in os.environ.items() if k.startswith("COVERAGE")}
        environment |= {"PYTHONPATH": os.pathsep.join(self._python_path())}
        environment |= dict(self.env)
        environment[self.data_dir_variable] = str(data_dir)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", self.ini_name, *args],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"alembic {' '.join(args)} failed with status {result.returncode}:\n"
                f"{result.stdout}{result.stderr}"
            )

    def _python_path(self) -> list[str]:
        """The project's ``prepend_sys_path`` entries made absolute, then the current path.

        Absolute, so the project's own modules still import when Alembic runs from a copy.
        """
        config = Config(str(self.directory / self.ini_name))
        entries = (config.get_main_option("prepend_sys_path") or "").split(os.pathsep)
        prepended = [str((self.directory / entry).resolve()) for entry in entries if entry]
        return [*prepended, *sys.path]

    def assert_single_head(self) -> None:
        """Fail unless the migrations have exactly one head.

        Two heads mean two migrations claim the same parent, and ``alembic upgrade head`` fails
        on a deployment rather than in CI.
        """
        heads = ScriptDirectory.from_config(self.config()).get_heads()
        assert len(heads) == 1, f"expected one migration head, found {len(heads)}: {heads}"

    def assert_models_match(self, metadata: MetaData, data_dir: Path) -> None:
        """Fail unless upgrading an empty database to head yields exactly ``metadata``'s schema."""
        self.alembic(data_dir, "upgrade", "head")
        engine = create_engine(self.sync_url(data_dir))
        try:
            with engine.connect() as connection:
                context = MigrationContext.configure(
                    connection, opts={"compare_type": True, "render_as_batch": True}
                )
                differences = compare_metadata(context, metadata)
        finally:
            engine.dispose()
        assert differences == [], (
            f"the models and the migrations disagree; generate a migration for: {differences}"
        )

    def assert_parent_rebuilds_keep_children(
        self,
        metadata: MetaData,
        data_dir: Path,
        scratch: Path,
        overrides: Mapping[str, Mapping[str, Any]] | None = None,
        extra_rows: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    ) -> None:
        """Fail if rebuilding a table that others point at loses or orphans their rows.

        SQLite's batch mode rebuilds a table by copying it, dropping the original and renaming
        the copy; with foreign keys on, the drop runs every ON DELETE rule pointing at it. This
        upgrades a database to head, puts one synthetic row in every table, then runs a copy of
        the migrations with one more that rebuilds every referenced table, and checks every row
        is still there.

        Rows are invented from column types. ``overrides`` supplies values for columns whose
        type or constraints the generator cannot satisfy: ``{"table": {"column": value}}``.
        ``extra_rows`` adds further rows to a table after its synthetic one, each a synthetic row
        with the given values on top, for a constraint one row per table cannot meet -- two
        different households for a row that must name two, say::

            extra_rows={"household": [{"id": 2}]},
            overrides={"settlement": {"to_id": 2}},

        ``scratch`` is an empty directory for the copy of the migrations.
        """
        parents = sorted(
            {fk.column.table.name for table in metadata.sorted_tables for fk in table.foreign_keys}
        )
        assert parents, "no table is referenced by a foreign key; there is nothing to check"

        self.alembic(data_dir, "upgrade", "head")
        engine = create_engine(self.sync_url(data_dir))
        try:
            with engine.begin() as connection:
                for table in metadata.sorted_tables:
                    row = synthetic_row(table, overrides)
                    connection.execute(table.insert().values(**row))
                    for extra in (extra_rows or {}).get(table.name, ()):
                        connection.execute(table.insert().values(**(row | dict(extra))))
            before = _row_counts(engine, metadata)

            copy = self._copy_with_rebuild(scratch, parents)
            self.alembic(data_dir, "upgrade", "head", directory=copy)

            after = _row_counts(engine, metadata)
        finally:
            engine.dispose()
        lost = {name: (before[name], after[name]) for name in before if after[name] != before[name]}
        assert not lost, (
            f"rebuilding {', '.join(parents)} changed row counts (before, after): {lost}"
        )

    def _copy_with_rebuild(self, scratch: Path, parents: list[str]) -> Path:
        """Copy the project's Alembic files into ``scratch`` and add the rebuilding migration."""
        config = self.config()
        source = Path(config.get_main_option("script_location") or "")
        head = ScriptDirectory.from_config(config).get_current_head()
        shutil.copy(self.directory / self.ini_name, scratch / self.ini_name)
        relative = source.relative_to(self.directory)
        shutil.copytree(source, scratch / relative)
        versions = scratch / relative / "versions"
        (versions / f"{REBUILD_REVISION}.py").write_text(
            "from alembic import op\n\n"
            f"revision = {REBUILD_REVISION!r}\n"
            f"down_revision = {head!r}\n"
            "branch_labels = None\n"
            "depends_on = None\n\n\n"
            "def upgrade():\n"
            f"    for name in {parents!r}:\n"
            "        with op.batch_alter_table(name, recreate='always'):\n"
            "            pass\n\n\n"
            "def downgrade():\n"
            "    pass\n",
            encoding="utf-8",
        )
        return scratch


def _row_counts(engine: Any, metadata: MetaData) -> dict[str, int]:
    """The number of rows in each of ``metadata``'s tables."""
    with engine.connect() as connection:
        return {
            table.name: connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in metadata.sorted_tables
        }


def synthetic_row(
    table: Table, overrides: Mapping[str, Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    """Values for one row of ``table`` that point every foreign key at the referenced table's row.

    Every table gets a row with integer primary keys of 1, so a foreign key column takes the
    value of the column it references in the row generated for that table. Nullable columns with
    no foreign key and columns with a server default are left out.
    """
    explicit = dict((overrides or {}).get(table.name, {}))
    row: dict[str, Any] = {}
    for column in table.columns:
        if column.name in explicit:
            row[column.name] = explicit[column.name]
        elif column.foreign_keys:
            # A column with several foreign keys points at the same value in each referenced row,
            # since every generated row has the same keys; the first one decides it.
            fk = sorted(column.foreign_keys, key=lambda key: key.target_fullname)[0]
            row[column.name] = _value_for(fk.column, table.name, overrides)
        elif column.primary_key or not (column.nullable or column.server_default is not None):
            row[column.name] = _value_for(column, table.name, overrides)
    return row


def _value_for(
    column: Column[Any], table_name: str, overrides: Mapping[str, Mapping[str, Any]] | None
) -> Any:
    """The value the generated row of ``column``'s table holds in it."""
    owner = column.table.name
    explicit = (overrides or {}).get(owner, {})
    if column.name in explicit:
        return explicit[column.name]
    column_type = column.type
    # Checked before the generic table below: Enum is a String, and UtcDateTime wraps DateTime.
    if isinstance(column_type, Enum):
        return column_type.enums[0]
    if isinstance(column_type, UtcDateTime):
        return datetime(2026, 1, 1, tzinfo=UTC)
    simple: list[tuple[type, Any]] = [
        (Boolean, True),
        (Integer, 1),
        (String, "x"),
        (DateTime, datetime(2026, 1, 1)),
        (Date, date(2026, 1, 1)),
        (Time, time(0, 0)),
        (Interval, timedelta(0)),
        # Float subclasses Numeric, so it comes first.
        (Float, 1.0),
        (Numeric, Decimal(1)),
        (LargeBinary, b"\x00"),
        (JSON, {}),
        (Uuid, uuid.UUID(int=1)),
    ]
    for kind, value in simple:
        if isinstance(column_type, kind):
            return value
    raise UnsupportedColumnError(
        f"no synthetic value for {owner}.{column.name} ({column_type!r}) while filling "
        f"{table_name}; pass one in overrides={{{owner!r}: {{{column.name!r}: ...}}}}"
    )
