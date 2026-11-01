"""Secrets an application generates for itself on first start and keeps in its data directory.

Generating on first start is what lets an application run with no configuration at all. The file
is never rewritten afterwards: whatever the secret protects (encrypted rows, signed tokens) is
lost with it.
"""

from __future__ import annotations

import logging
import os
import secrets
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

#: Random bytes in a generated secret, before URL-safe base64 encoding.
SECRET_BYTES = 48


class SecretFileError(RuntimeError):
    """A secret file exists but holds nothing usable."""


def load_or_create_secret(path: Path, nbytes: int = SECRET_BYTES) -> str:
    """Return the secret in ``path``, generating it there first if the file does not exist.

    The secret is written to a temporary owner-only file beside ``path`` and hard-linked into
    place. The link either succeeds with the whole secret already in the file, or fails because
    the file exists, so when two processes start at once one creates the secret and the other
    reads it, and neither ever sees a half-written file.

    An existing empty file is an error rather than something to overwrite: the secret it should
    hold may already protect data, and replacing it would silently make that data unreadable.
    """
    try:
        return _read(path)
    except FileNotFoundError:
        pass

    path.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(nbytes)
    # mkstemp creates the file 0600, so the secret is never readable by anyone else.
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(secret)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            return _read(path)
    finally:
        os.unlink(temporary)
    logger.info("generated a new secret at %s", path)
    return secret


def _read(path: Path) -> str:
    """The secret in ``path``, which must not be empty."""
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise SecretFileError(f"{path} is empty; restore it, or delete it to generate a new one")
    return value
