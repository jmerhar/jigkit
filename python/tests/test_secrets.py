"""load_or_create_secret."""

import os
import stat
from pathlib import Path

import pytest

from jigkit import secrets as jigkit_secrets
from jigkit.secrets import SecretFileError, load_or_create_secret


def test_generates_an_owner_only_secret(tmp_path: Path) -> None:
    path = tmp_path / "keys" / "secret.key"

    secret = load_or_create_secret(path)

    assert len(secret) >= 64
    assert path.read_text() == secret
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_returns_the_existing_secret_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "secret.key"
    path.write_text("kept\n")

    assert load_or_create_secret(path) == "kept"
    assert path.read_text() == "kept\n"


def test_an_empty_secret_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "secret.key"
    path.write_text("")

    with pytest.raises(SecretFileError, match="is empty"):
        load_or_create_secret(path)


def test_losing_the_race_returns_the_winners_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "secret.key"
    real_link = os.link

    def another_process_wins(source: str, target: Path) -> None:
        # The other process links its secret in between this one's check and its own link.
        Path(target).write_text("winner")
        real_link(source, target)

    monkeypatch.setattr(jigkit_secrets.os, "link", another_process_wins)

    assert load_or_create_secret(path) == "winner"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["secret.key"]


def test_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    load_or_create_secret(tmp_path / "secret.key")

    assert sorted(p.name for p in tmp_path.iterdir()) == ["secret.key"]
