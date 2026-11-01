"""Where an application's log goes, and how its level changes while it runs.

Two destinations. The stream is what ``docker logs`` shows. The file survives the container
being recreated; it belongs in the mounted data directory, so it can be read from the host, and
it rotates, because nothing else rotates a file inside a container.

The level can change at runtime, because the moment DEBUG is needed is the moment something is
failing, and restarting to get it loses whatever state was interesting.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"

#: The levels an application offers to choose from.
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

#: Five files of five megabytes.
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

#: Loggers that hold a level of their own and so are set alongside the root; uvicorn gives its
#: access and error loggers one, and raising the root alone would leave them where they were.
FOLLOW_ROOT = ("uvicorn", "uvicorn.access", "uvicorn.error")

#: Loggers held at WARNING however low the application goes. httpx logs every request's URL at
#: INFO and httpcore logs headers at DEBUG, and URLs and headers carry credentials: push-monitor
#: tokens, bot tokens, session cookies.
QUIET = ("httpx", "httpcore")

# Marks the handlers this module installed, so a repeated call replaces them rather than stacking
# a second copy that logs every line twice.
_MARKER = "_jigkit_handler"


def configure_logging(
    level: str = "INFO",
    *,
    log_file: Path | None = None,
    quiet: Iterable[str] = QUIET,
    max_bytes: int = MAX_BYTES,
    backup_count: int = BACKUP_COUNT,
) -> Path | None:
    """Install the stream handler, and the rotating file handler when ``log_file`` is given.

    Idempotent: calling it again replaces the handlers it installed rather than adding more.
    Returns the file's path, or None when there is no file or it could not be opened. An
    unwritable data directory does not stop the application, since the stream still carries
    everything.
    """
    quiet = tuple(quiet)
    apply_level(level, quiet=quiet)

    root = logging.getLogger()
    for handler in [h for h in root.handlers if getattr(h, _MARKER, False)]:
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(FORMAT)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    setattr(stream, _MARKER, True)
    root.addHandler(stream)

    if log_file is None:
        return None
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
    except OSError:
        logging.getLogger(__name__).warning(
            "could not open %s for writing; logging to the stream only", log_file, exc_info=True
        )
        return None
    file_handler.setFormatter(formatter)
    setattr(file_handler, _MARKER, True)
    root.addHandler(file_handler)
    return log_file


def apply_level(level: str, *, quiet: Iterable[str] = QUIET) -> int:
    """Set the level of the root logger and of the loggers that follow it, and return it.

    The ``quiet`` loggers never go below WARNING.
    """
    resolved = resolve_level(level)
    logging.getLogger().setLevel(resolved)
    for name in FOLLOW_ROOT:
        logging.getLogger(name).setLevel(resolved)
    for name in quiet:
        logging.getLogger(name).setLevel(max(resolved, logging.WARNING))
    return resolved


def resolve_level(level: str) -> int:
    """The numeric level for a name, INFO for anything unrecognised."""
    value = logging.getLevelNamesMapping().get(level.strip().upper())
    return value if value is not None else logging.INFO
