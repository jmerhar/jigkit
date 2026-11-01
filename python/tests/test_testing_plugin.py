"""The pytest plugin's fixtures."""

import socket
import tempfile
from pathlib import Path

import pytest

from jigkit.testing import NetworkAccessError, _is_allowed, _is_local


def test_data_dir_is_an_empty_directory(data_dir: Path) -> None:
    assert data_dir.is_dir()
    assert list(data_dir.iterdir()) == []


class TestNoNetwork:
    @pytest.mark.usefixtures("no_network")
    def test_connecting_to_another_host_fails(self) -> None:
        with (
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
            pytest.raises(NetworkAccessError, match="192.0.2.1"),
        ):
            sock.connect(("192.0.2.1", 80))

    @pytest.mark.usefixtures("no_network")
    def test_connect_ex_to_another_host_fails(self) -> None:
        with (
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
            pytest.raises(NetworkAccessError),
        ):
            sock.connect_ex(("192.0.2.1", 80))

    @pytest.mark.usefixtures("no_network")
    @pytest.mark.parametrize("host", ["example.com", b"example.com"])
    def test_resolving_another_host_fails(self, host: str | bytes) -> None:
        with pytest.raises(NetworkAccessError, match="example.com"):
            socket.getaddrinfo(host, 443)

    @pytest.mark.usefixtures("no_network")
    def test_loopback_stays_open(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            assert socket.getaddrinfo("localhost", port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.connect(("127.0.0.1", port))
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                assert client.connect_ex(("127.0.0.1", port)) == 0

    @pytest.mark.usefixtures("no_network")
    def test_unix_sockets_stay_open(self) -> None:
        # Under /tmp, because macOS limits a socket path to about 100 characters and pytest's
        # temporary directories are longer.
        with (
            tempfile.TemporaryDirectory(dir="/tmp") as directory,
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener,
        ):
            path = f"{directory}/s"
            listener.bind(path)
            listener.listen()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(path)

    @pytest.mark.usefixtures("no_network")
    def test_resolving_no_host_is_allowed(self) -> None:
        assert socket.getaddrinfo(None, 80)

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("localhost", True),
            ("127.0.0.53", True),
            ("::1", True),
            ("::1%lo0", True),
            ("10.0.0.1", False),
            ("example.com", False),
            (None, False),
        ],
    )
    def test_is_local(self, host: object, expected: bool) -> None:
        assert _is_local(host) is expected


@pytest.mark.parametrize(
    ("family", "address", "expected"),
    [
        (socket.AF_INET, ("127.0.0.1", 80), True),
        (socket.AF_INET, ("192.0.2.1", 80), False),
        (socket.AF_UNIX, "/run/app.sock", True),
        # Any address that is not a host and port is refused rather than guessed at.
        (socket.AF_INET, "127.0.0.1", False),
        (socket.AF_INET, (), False),
    ],
)
def test_is_allowed(family: int, address: object, expected: bool) -> None:
    assert _is_allowed(family, address) is expected
