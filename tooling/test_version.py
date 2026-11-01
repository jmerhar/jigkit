"""bin/version.py: one version in every manifest, released from the changelog."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

BIN = Path(__file__).parents[1] / "bin"
_spec = importlib.util.spec_from_file_location("version", BIN / "version.py")
assert _spec is not None and _spec.loader is not None
version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(version)

CHANGELOG = """# Changelog

Intro.

## Unreleased

### Added

- Something new.

## 0.1.0 — 2026-11-01

- The first release.
"""

TODAY = date(2026, 11, 2)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A checkout at 0.2.0.dev0 with an Unreleased section waiting."""
    (tmp_path / "python").mkdir()
    (tmp_path / "python" / "pyproject.toml").write_text(
        '[project]\nname = "jigkit"\nversion = "0.2.0.dev0"\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    return tmp_path


def _pyproject_version(root: Path) -> str:
    return version.versions(root)["python/pyproject.toml"]


class TestCheck:
    def test_reports_the_version_every_manifest_names(self, root: Path) -> None:
        assert version.check(root, None) == "0.2.0.dev0"

    def test_a_tag_must_match_the_manifests(self, root: Path) -> None:
        with pytest.raises(version.VersionError, match="the tag is v0.3.0"):
            version.check(root, "v0.3.0")

    def test_a_tag_needs_its_dated_changelog_section(self, root: Path) -> None:
        version.set_version(root, "0.2.0", TODAY)
        (root / "CHANGELOG.md").write_text(CHANGELOG)

        with pytest.raises(version.VersionError, match="no dated section for 0.2.0"):
            version.check(root, "v0.2.0")

    def test_manifests_that_disagree_are_reported(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (root / "js").mkdir()
        (root / "js" / "version.txt").write_text("0.1.0\n")
        monkeypatch.setitem(
            version.MANIFESTS, "js/version.txt", version.re.compile(r"(?m)^()([^\n]*)()$")
        )

        with pytest.raises(version.VersionError, match="different versions"):
            version.check(root, None)

    def test_a_missing_manifest_is_reported(self, root: Path) -> None:
        (root / "python" / "pyproject.toml").unlink()

        with pytest.raises(version.VersionError, match="pyproject.toml is missing"):
            version.check(root, None)

    def test_a_manifest_without_a_version_is_reported(self, root: Path) -> None:
        (root / "python" / "pyproject.toml").write_text('[project]\nname = "jigkit"\n')

        with pytest.raises(version.VersionError, match="names no version"):
            version.check(root, None)


class TestSet:
    def test_releases_the_development_version_it_names(self, root: Path) -> None:
        version.set_version(root, "0.2.0", TODAY)

        assert _pyproject_version(root) == "0.2.0"
        changelog = (root / "CHANGELOG.md").read_text()
        assert "## 0.2.0 — 2026-11-02\n\n### Added" in changelog
        assert "## Unreleased" not in changelog

    def test_a_version_before_the_current_one_is_refused(self, root: Path) -> None:
        with pytest.raises(version.VersionError, match="not after 0.2.0.dev0"):
            version.set_version(root, "0.1.9", TODAY)

    def test_a_release_cannot_be_cut_twice(self, root: Path) -> None:
        version.set_version(root, "0.2.0", TODAY)

        with pytest.raises(version.VersionError, match="not after 0.2.0"):
            version.set_version(root, "0.2.0", TODAY)

    @pytest.mark.parametrize("wanted", ["1.2", "v1.2.3", "1.2.3.dev0"])
    def test_only_a_plain_release_version_is_accepted(self, root: Path, wanted: str) -> None:
        with pytest.raises(version.VersionError, match="not a version like 1.2.3"):
            version.set_version(root, wanted, TODAY)

    def test_an_unrecognised_current_version_is_reported(self, root: Path) -> None:
        (root / "python" / "pyproject.toml").write_text('version = "0.2.0rc1"\n')

        with pytest.raises(version.VersionError, match="neither a release"):
            version.set_version(root, "0.2.0", TODAY)

    @pytest.mark.parametrize(
        ("changelog", "message"),
        [
            ("# Changelog\n", "no '## Unreleased' section"),
            ("## Unreleased\n\n- a\n\n## Unreleased\n\n- b\n", "more than one"),
            ("## Unreleased\n\n### Added\n\n## 0.1.0 — 2026-11-01\n", "section is empty"),
            ("## Unreleased\n\n- a\n\n## 0.3.0 — 2026-11-01\n", "already has a section"),
        ],
    )
    def test_a_changelog_that_cannot_be_released_changes_nothing(
        self, root: Path, changelog: str, message: str
    ) -> None:
        (root / "CHANGELOG.md").write_text(changelog)

        with pytest.raises(version.VersionError, match=message):
            version.set_version(root, "0.3.0", TODAY)
        assert _pyproject_version(root) == "0.2.0.dev0"
        assert (root / "CHANGELOG.md").read_text() == changelog


class TestNotes:
    def test_prints_the_section_without_its_heading(self, root: Path) -> None:
        assert version.notes(root, "0.1.0") == "- The first release.\n"

    def test_an_undated_or_missing_section_is_an_error(self, root: Path) -> None:
        with pytest.raises(version.VersionError, match="no dated section for 0.9.0"):
            version.notes(root, "0.9.0")


class TestCommandLine:
    def test_check(self, root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert version.main(["--root", str(root), "check"]) == 0
        assert "every manifest names 0.2.0.dev0" in capsys.readouterr().out

    def test_set_then_notes(self, root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert version.main(["--root", str(root), "set", "0.2.0"]) == 0
        assert version.main(["--root", str(root), "notes", "0.2.0"]) == 0
        assert "- Something new." in capsys.readouterr().out

    def test_an_error_is_reported_and_exits_1(
        self, root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert version.main(["--root", str(root), "check", "v9.9.9"]) == 1
        assert "the tag is v9.9.9" in capsys.readouterr().err
