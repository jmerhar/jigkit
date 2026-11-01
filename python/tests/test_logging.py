"""configure_logging and apply_level."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from jigkit.logging import (
    FOLLOW_ROOT,
    QUIET,
    apply_level,
    configure_logging,
    resolve_level,
)


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """Put the root logger's handlers and every touched level back after each test."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    others = {name: logging.getLogger(name).level for name in (*FOLLOW_ROOT, *QUIET)}
    yield
    for handler in root.handlers:
        if handler not in handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)
    for name, previous in others.items():
        logging.getLogger(name).setLevel(previous)


def _ours() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, "_jigkit_handler", False)]


class TestConfigureLogging:
    def test_writes_to_the_file_it_returns(self, tmp_path: Path) -> None:
        log_file = tmp_path / "logs" / "app.log"

        assert configure_logging("INFO", log_file=log_file) == log_file
        logging.getLogger("jigkit.test").info("hello file")
        for handler in _ours():
            handler.flush()

        assert "hello file" in log_file.read_text()

    def test_calling_it_again_replaces_its_handlers(self, tmp_path: Path) -> None:
        configure_logging("INFO", log_file=tmp_path / "a.log")
        configure_logging("INFO", log_file=tmp_path / "b.log")

        assert len(_ours()) == 2

    def test_without_a_file_it_logs_to_the_stream_only(self) -> None:
        assert configure_logging("INFO") is None
        assert [type(h) for h in _ours()] == [logging.StreamHandler]

    def test_an_unwritable_file_falls_back_to_the_stream(self, tmp_path: Path) -> None:
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("")

        assert configure_logging("INFO", log_file=blocker / "app.log") is None
        assert len(_ours()) == 1


class TestLevels:
    def test_followers_move_with_the_root(self) -> None:
        apply_level("DEBUG")

        assert logging.getLogger().level == logging.DEBUG
        assert all(logging.getLogger(name).level == logging.DEBUG for name in FOLLOW_ROOT)

    def test_quiet_loggers_never_go_below_warning(self) -> None:
        apply_level("DEBUG")

        assert all(logging.getLogger(name).level == logging.WARNING for name in QUIET)

    def test_quiet_loggers_go_above_warning_with_the_root(self) -> None:
        apply_level("ERROR")

        assert all(logging.getLogger(name).level == logging.ERROR for name in QUIET)

    def test_a_custom_quiet_list(self) -> None:
        apply_level("DEBUG", quiet=["jigkit.test.chatty"])

        assert logging.getLogger("jigkit.test.chatty").level == logging.WARNING

    @pytest.mark.parametrize(
        ("name", "expected"),
        [("debug", logging.DEBUG), (" Warning ", logging.WARNING), ("loud", logging.INFO)],
    )
    def test_resolve_level(self, name: str, expected: int) -> None:
        assert resolve_level(name) == expected
