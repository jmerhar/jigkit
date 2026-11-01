"""The container health probe, against a real local HTTP server."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from jigkit.healthcheck import main, probe


class Health(BaseHTTPRequestHandler):
    """Answers with whatever status and body the server was given."""

    def do_GET(self) -> None:  # noqa: N802
        status, body = self.server.reply  # type: ignore[attr-defined]
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if body is not None:
            self.wfile.write(body.encode())

    def log_message(self, *args: object) -> None:
        """Keep the test output clean."""


@pytest.fixture
def server() -> Iterator[ThreadingHTTPServer]:
    """A health endpoint on a free loopback port; set ``server.reply`` to choose its answer."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Health)
    httpd.reply = (200, json.dumps({"status": "ok", "database": "connected"}))  # type: ignore[attr-defined]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def _url(server: ThreadingHTTPServer) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}/health"


class TestProbe:
    def test_healthy_when_every_expectation_holds(self, server: ThreadingHTTPServer) -> None:
        assert probe(_url(server), {"database": "connected", "status": "ok"}) == 0

    def test_healthy_with_no_expectations(self, server: ThreadingHTTPServer) -> None:
        assert probe(_url(server)) == 0

    def test_unhealthy_when_a_value_differs(
        self, server: ThreadingHTTPServer, capsys: pytest.CaptureFixture[str]
    ) -> None:
        server.reply = (200, json.dumps({"database": "unreachable"}))  # type: ignore[attr-defined]

        assert probe(_url(server), {"database": "connected"}) == 1
        assert "database is 'unreachable', expected 'connected'" in capsys.readouterr().err

    def test_unhealthy_on_an_error_status(
        self, server: ThreadingHTTPServer, capsys: pytest.CaptureFixture[str]
    ) -> None:
        server.reply = (503, json.dumps({"database": "connected"}))  # type: ignore[attr-defined]

        assert probe(_url(server)) == 1
        assert "HTTP 503" in capsys.readouterr().err

    def test_unhealthy_on_a_success_that_is_not_200(self, server: ThreadingHTTPServer) -> None:
        server.reply = (204, None)  # type: ignore[attr-defined]

        assert probe(_url(server)) == 1

    def test_unhealthy_on_a_body_that_is_not_json(self, server: ThreadingHTTPServer) -> None:
        server.reply = (200, "<html>")  # type: ignore[attr-defined]

        assert probe(_url(server)) == 1

    def test_unhealthy_on_json_that_is_not_an_object(
        self, server: ThreadingHTTPServer, capsys: pytest.CaptureFixture[str]
    ) -> None:
        server.reply = (200, "[]")  # type: ignore[attr-defined]

        assert probe(_url(server)) == 1
        assert "expected a JSON object, got list" in capsys.readouterr().err

    def test_unhealthy_when_nothing_listens(self, server: ThreadingHTTPServer) -> None:
        url = _url(server)
        server.shutdown()
        server.server_close()

        assert probe(url, timeout=1) == 1


class TestCommandLine:
    def test_expectations_are_read_as_json_when_they_are_json(
        self, server: ThreadingHTTPServer
    ) -> None:
        server.reply = (200, json.dumps({"ready": True, "workers": 2, "mode": "live"}))  # type: ignore[attr-defined]

        args = [_url(server), "--expect", "ready=true", "--expect", "workers=2"]
        assert main([*args, "--expect", "mode=live"]) == 0
        assert main([_url(server), "--expect", "ready=false"]) == 1

    def test_a_malformed_expectation_is_a_usage_error(self, server: ThreadingHTTPServer) -> None:
        with pytest.raises(SystemExit) as raised:
            main([_url(server), "--expect", "no-equals-sign"])

        assert raised.value.code == 2
