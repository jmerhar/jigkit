"""The pytest plugin for applications built on jigkit (extra ``testing``).

Load it from the application's ``conftest.py``::

    pytest_plugins = ["jigkit.testing"]

It provides fixtures; the migration checks are in :mod:`jigkit.testing.migrations`. Fixtures an
application defines under the same name in its own conftest take precedence.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

#: Host names a test may still resolve and connect to under :func:`no_network`.
LOCAL_NAMES = frozenset({"localhost", "localhost.localdomain", ""})


class NetworkAccessError(AssertionError):
    """A test tried to reach a host other than this machine."""


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A throwaway data directory, created and empty."""
    directory = tmp_path / "data"
    directory.mkdir()
    return directory


def _is_local(host: object) -> bool:
    """Whether ``host`` (a name or an address) is this machine."""
    if not isinstance(host, str):
        return False
    if host.lower() in LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _is_allowed(family: int, address: Any) -> bool:
    """Whether a socket address of ``family`` stays on this machine."""
    if family == getattr(socket, "AF_UNIX", object()):
        return True
    if isinstance(address, tuple) and address:
        return _is_local(address[0])
    return False


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail the test if it resolves or connects to anything but this machine.

    A suite that quietly reaches the network depends on DNS and on hosts it does not control,
    and sends traffic to whatever host a fixture names. Loopback stays open, so tests can still
    talk to a server they started themselves. Request it per test, or make it autouse in the
    application's conftest.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self: socket.socket, address: Any) -> None:
        if not _is_allowed(self.family, address):
            raise NetworkAccessError(f"test tried to connect to {address!r}")
        real_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any) -> int:
        if not _is_allowed(self.family, address):
            raise NetworkAccessError(f"test tried to connect to {address!r}")
        return real_connect_ex(self, address)

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        name = host.decode() if isinstance(host, bytes) else host
        if name is not None and not _is_local(name):
            raise NetworkAccessError(f"test tried to resolve {name!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield
