"""jigkit.migrations and the checks in jigkit.testing.migrations, run against the sample app."""

import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
import sample_schema
from alembic import command
from alembic.config import Config
from conftest import SAMPLE_APP
from sqlalchemy import Column, Integer, MetaData, PickleType, Table

from jigkit.migrations import _ensure_sqlite_directory, render_item
from jigkit.models import NAMING_CONVENTION, UtcDateTime
from jigkit.testing.migrations import (
    MigrationProject,
    UnsupportedColumnError,
    synthetic_row,
)

PROJECT = MigrationProject(SAMPLE_APP, database_filename="sample.db")

#: The sample application's tables, apart from any other test module's on the shared Base.
SAMPLE_TABLES = ("owners", "pets", "notes")


def sample_metadata() -> MetaData:
    """The sample application's schema on a metadata of its own."""
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    for name in SAMPLE_TABLES:
        sample_schema.Base.metadata.tables[name].to_metadata(metadata)
    return metadata


def copy_project(destination: Path) -> MigrationProject:
    """A copy of the sample project, for tests that add migrations to it."""
    shutil.copytree(SAMPLE_APP, destination, ignore=shutil.ignore_patterns("__pycache__"))
    return MigrationProject(destination, database_filename="sample.db")


def add_migration(project: MigrationProject, revision: str, down: str | None, body: str) -> None:
    """Write a migration with ``body`` as its upgrade into ``project``."""
    (project.directory / "alembic" / "versions" / f"{revision}.py").write_text(
        "from alembic import op\n"
        f"revision = {revision!r}\ndown_revision = {down!r}\n"
        "branch_labels = None\ndepends_on = None\n"
        f"def upgrade():\n    {body}\n"
        "def downgrade():\n    pass\n"
    )


class TestRunMigrations:
    def test_upgrades_into_a_data_directory_that_does_not_exist_yet(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "not" / "yet"

        PROJECT.alembic(data_dir, "upgrade", "head")

        with closing(sqlite3.connect(data_dir / "sample.db")) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        assert set(SAMPLE_TABLES) <= tables

    def test_offline_mode_writes_nothing(self, data_dir: Path) -> None:
        # Offline mode prints the SQL instead of running it, so no database file appears; a
        # failing run would raise.
        PROJECT.alembic(data_dir, "upgrade", "head", "--sql")

        assert not (data_dir / "sample.db").exists()

    def test_rows_left_pointing_at_nothing_fail_the_upgrade(
        self, data_dir: Path, tmp_path: Path
    ) -> None:
        project = copy_project(tmp_path / "project")
        add_migration(
            project,
            "0002",
            "0001",
            "op.execute(\"INSERT INTO notes (id, owner_id, body) VALUES (1, 99, 'orphan')\")",
        )

        with pytest.raises(AssertionError, match="rows pointing at nothing"):
            project.alembic(data_dir, "upgrade", "head")

    def test_runs_without_an_ini_file(
        self, data_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Alembic driven from code, with no alembic.ini and so no logging section to apply.
        monkeypatch.setenv("DATA_DIR", str(data_dir))
        config = Config()
        config.set_main_option("script_location", str(SAMPLE_APP / "alembic"))

        command.upgrade(config, "head")

        assert (data_dir / "sample.db").exists()

    def test_render_item_writes_utc_datetime_as_plain_datetime(self) -> None:
        assert render_item("type", UtcDateTime(), None) == "sa.DateTime()"
        assert render_item("type", Integer(), None) is False
        assert render_item("column", UtcDateTime(), None) is False

    @pytest.mark.parametrize(
        "url", ["sqlite://", "sqlite:///:memory:", "sqlite:///file:x?uri=true"]
    )
    def test_no_directory_is_made_for_a_database_without_a_file(
        self, url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        _ensure_sqlite_directory(url)

        assert list(tmp_path.iterdir()) == []


class TestModelsMatch:
    def test_passes_when_the_migrations_produce_the_models(self, data_dir: Path) -> None:
        PROJECT.assert_models_match(sample_metadata(), data_dir)

    def test_fails_for_a_model_change_without_a_migration(self, data_dir: Path) -> None:
        metadata = sample_metadata()
        Table("extra", metadata, Column("id", Integer, primary_key=True))

        with pytest.raises(AssertionError, match="disagree"):
            PROJECT.assert_models_match(metadata, data_dir)


class TestSingleHead:
    def test_passes_with_one_head(self) -> None:
        PROJECT.assert_single_head()

    def test_fails_with_two(self, tmp_path: Path) -> None:
        project = copy_project(tmp_path / "project")
        add_migration(project, "0002a", "0001", "pass")
        add_migration(project, "0002b", "0001", "pass")

        with pytest.raises(AssertionError, match="found 2"):
            project.assert_single_head()


class TestParentRebuilds:
    def test_passes_when_migrations_run_through_jigkit(
        self, data_dir: Path, tmp_path: Path
    ) -> None:
        PROJECT.assert_parent_rebuilds_keep_children(sample_metadata(), data_dir, tmp_path)

    def test_fails_when_foreign_keys_stay_on(self, data_dir: Path, tmp_path: Path) -> None:
        # Alembic's stock environment, which jigkit replaces, deletes the pets and orphans the
        # notes when it rebuilds their owner.
        project = MigrationProject(
            SAMPLE_APP, database_filename="sample.db", env={"SAMPLE_PLAIN_ENV": "1"}
        )

        with pytest.raises(AssertionError, match=r"'pets': \(1, 0\)"):
            project.assert_parent_rebuilds_keep_children(sample_metadata(), data_dir, tmp_path)

    def test_extra_rows_meet_a_constraint_one_row_per_table_cannot(
        self, data_dir: Path, tmp_path: Path
    ) -> None:
        # A note that must not belong to the owner of pet 1: the second owner is an extra row,
        # and the note points at it.
        project = copy_project(tmp_path / "project")
        add_migration(
            project,
            "0002",
            "0001",
            "op.execute('CREATE TRIGGER different BEFORE INSERT ON notes WHEN NEW.owner_id = 1 "
            "BEGIN SELECT RAISE(ABORT, \\'the first owner takes no notes\\'); END')",
        )
        scratch = tmp_path / "scratch"
        scratch.mkdir()

        with pytest.raises(Exception, match="the first owner takes no notes"):
            project.assert_parent_rebuilds_keep_children(sample_metadata(), data_dir, scratch)

        again = tmp_path / "again"
        again.mkdir()
        project.assert_parent_rebuilds_keep_children(
            sample_metadata(),
            tmp_path / "data2",
            again,
            extra_rows={"owners": [{"id": 2, "name": "second"}]},
            overrides={"notes": {"owner_id": 2}},
        )

    def test_needs_a_table_that_something_points_at(self, data_dir: Path, tmp_path: Path) -> None:
        metadata = MetaData()
        Table("alone", metadata, Column("id", Integer, primary_key=True))

        with pytest.raises(AssertionError, match="nothing to check"):
            PROJECT.assert_parent_rebuilds_keep_children(metadata, data_dir, tmp_path)

    def test_a_failing_alembic_run_reports_its_output(self, data_dir: Path, tmp_path: Path) -> None:
        project = copy_project(tmp_path / "project")
        add_migration(project, "0002", "0001", "raise RuntimeError('broken migration')")

        with pytest.raises(AssertionError, match="broken migration"):
            project.alembic(data_dir, "upgrade", "head")


class TestSyntheticRows:
    def test_foreign_keys_point_at_the_parent_row(self) -> None:
        metadata = sample_metadata()

        pet = synthetic_row(metadata.tables["pets"])
        note = synthetic_row(metadata.tables["notes"])

        assert pet["owner_id"] == 1
        assert pet["kind"] == "CAT"
        assert note == {"id": 1, "owner_id": 1, "body": "x"}

    def test_optional_columns_are_left_out(self) -> None:
        owner = synthetic_row(sample_metadata().tables["owners"])

        assert "nickname" not in owner

    def test_overrides_win_for_the_table_and_for_the_columns_pointing_at_it(self) -> None:
        metadata = sample_metadata()
        overrides = {"owners": {"id": 7}, "notes": {"body": "hello"}}

        assert synthetic_row(metadata.tables["owners"], overrides)["id"] == 7
        assert synthetic_row(metadata.tables["notes"], overrides) == {
            "id": 1,
            "owner_id": 7,
            "body": "hello",
        }

    def test_an_unknown_type_asks_for_an_override(self) -> None:
        table = Table(
            "blobs",
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("value", PickleType, nullable=False),
        )

        with pytest.raises(UnsupportedColumnError, match=r"overrides=\{'blobs': \{'value'"):
            synthetic_row(table)
