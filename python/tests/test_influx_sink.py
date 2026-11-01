"""Writing line protocol to InfluxDB 3 and 2.x, against a real HTTP server."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable

import pytest

from jigkit.influx.sink import ERROR_EXCERPT, Influx2Sink, Influx3Sink, InfluxSink, classify
from jigkit.sinks import Outcome, Point, Precision
from jigkit.testing.http import StubServer

LINE = "indoor,station=home temp_c=23.2 1791500484"
ROWS = [
    Point(
        "indoor", (("station", "home"),), 1791500484, {"temp_c": 23.2}, precision=Precision.SECONDS
    )
]
KINDS = ("influx3", "influx2")


@pytest.fixture
async def store_for_stub(influx: StubServer) -> AsyncIterator[Callable[..., InfluxSink]]:
    """Builds sinks of either version pointed at the stand-in, and closes them afterwards."""
    made: list[InfluxSink] = []

    def make(kind: str = "influx3", **overrides: str) -> InfluxSink:
        connection = {"url": influx.url, "database": "weather", "token": "apiv3_test"}
        connection |= overrides
        org = connection.pop("org", "")
        if kind == "influx3":
            made.append(Influx3Sink(**connection))
        else:
            made.append(Influx2Sink(**connection, org=org))
        return made[-1]

    yield make
    for store in made:
        await store.aclose()


async def test_v3_writes_line_protocol_with_a_bearer_token(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    assert await store_for_stub().write(ROWS) is Outcome.OK

    (request,) = influx.requests
    assert (request.method, request.path) == ("POST", "/api/v3/write_lp")
    assert request.query == {"db": "weather", "precision": "second"}
    assert request.headers["authorization"] == "Bearer apiv3_test"
    assert request.headers["content-type"].startswith("text/plain")
    assert request.body == LINE


async def test_v2_writes_to_a_bucket_with_a_token_scheme(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    store = store_for_stub("influx2", org="home", database="wx")

    assert await store.write(ROWS) is Outcome.OK

    (request,) = influx.requests
    assert request.path == "/api/v2/write"
    assert request.query == {"bucket": "wx", "org": "home", "precision": "s"}
    assert request.headers["authorization"] == "Token apiv3_test"


@pytest.mark.parametrize("kind", KINDS)
async def test_no_token_sends_no_authorization(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink], kind: str
) -> None:
    """An InfluxDB with authentication disabled needs none, and an empty header would be wrong."""
    await store_for_stub(kind, token="").write(ROWS)

    assert "authorization" not in influx.requests[0].headers


async def test_a_trailing_slash_on_the_url_is_tolerated(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    await store_for_stub(url=influx.url + "/").write(ROWS)

    assert influx.requests[0].path == "/api/v3/write_lp"


async def test_a_rejected_write_reports_failure_with_the_reason(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink], caplog: pytest.LogCaptureFixture
) -> None:
    influx.status, influx.reply = 400, "partial write: field type conflict"
    store = store_for_stub()

    assert await store.write(ROWS) is Outcome.REJECT
    assert store.last_error is not None and "field type conflict" in store.last_error
    assert "HTTP 400" in caplog.text
    assert "not retrying" in caplog.text


async def test_a_long_error_body_is_truncated(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    influx.status, influx.reply = 502, "<html>" + "x" * 5000
    store = store_for_stub()

    await store.write(ROWS)

    assert store.last_error is not None
    assert len(store.last_error) <= ERROR_EXCERPT + len("HTTP 502: ")


async def test_a_success_clears_the_last_error(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    store = store_for_stub()
    influx.status = 500
    await store.write(ROWS)
    influx.status = 204

    assert await store.write(ROWS) is Outcome.OK
    assert store.last_error is None


async def test_an_unreachable_server_is_a_failure_not_an_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Port 1 refuses connections; a caller's own work must not depend on the database."""
    store = Influx3Sink("http://127.0.0.1:1", "weather")
    try:
        with caplog.at_level(logging.ERROR):
            assert await store.write(ROWS) is Outcome.RETRY
    finally:
        await store.aclose()

    assert store.last_error is not None and "ConnectError" in store.last_error


async def test_nothing_to_write_is_not_sent(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    assert await store_for_stub().write([]) is Outcome.OK
    assert influx.requests == []


async def test_without_a_url_nothing_is_attempted() -> None:
    store = Influx3Sink("", "weather")
    try:
        assert store.configured is False
        assert await store.write(ROWS) is Outcome.RETRY
        assert store.last_error == "no database is configured"
    finally:
        await store.aclose()


async def test_rows_without_fields_send_nothing(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    empty = [Point("indoor", (("station", "home"),), 1791500484, {}, precision=Precision.SECONDS)]

    assert await store_for_stub().write(empty) is Outcome.OK
    assert influx.requests == []


@pytest.mark.parametrize(("kind", "spelt"), [("influx3", "millisecond"), ("influx2", "ms")])
async def test_points_are_written_in_their_own_precision(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink], kind: str, spelt: str
) -> None:
    """A timestamp taken at the source in milliseconds reaches the database as one."""
    point = Point("meter", (), 1791500484123, {"w": 1.0}, precision=Precision.MILLISECONDS)

    assert await store_for_stub(kind, org="home").write([point]) is Outcome.OK

    (request,) = influx.requests
    assert request.query["precision"] == spelt
    assert request.body == "meter w=1.0 1791500484123"


async def test_flush_sends_nothing(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    await store_for_stub().flush()

    assert influx.requests == []


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (200, Outcome.OK),
        (204, Outcome.OK),
        (400, Outcome.REJECT),
        (413, Outcome.REJECT),
        (422, Outcome.REJECT),
        (401, Outcome.RETRY),
        (403, Outcome.RETRY),
        (404, Outcome.RETRY),
        (408, Outcome.RETRY),
        (429, Outcome.RETRY),
        (500, Outcome.RETRY),
        (503, Outcome.RETRY),
    ],
)
def test_classify(status: int, outcome: Outcome) -> None:
    """Data the server refuses is rejected; everything someone could fix is retried."""
    assert classify(status) is outcome


@pytest.mark.parametrize(
    ("status", "outcome"), [(503, Outcome.RETRY), (401, Outcome.RETRY), (422, Outcome.REJECT)]
)
async def test_write_reports_the_classified_outcome(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink], status: int, outcome: Outcome
) -> None:
    influx.status = status

    assert await store_for_stub().write(ROWS) is outcome


@pytest.mark.parametrize("kind", KINDS)
async def test_a_check_sends_an_empty_write_and_accepts_its_refusal_for_being_empty(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink], kind: str
) -> None:
    """InfluxDB checks token and database before the body; 'empty' means both were fine."""
    influx.status, influx.reply = 400, "incoming write was empty"

    assert await store_for_stub(kind, org="home").check() is None
    assert influx.requests[0].body == ""


async def test_a_check_accepts_a_server_that_takes_an_empty_write(
    influx: StubServer, store_for_stub: Callable[..., InfluxSink]
) -> None:
    influx.status = 204

    assert await store_for_stub().check() is None


@pytest.mark.parametrize(
    ("status", "reply", "reason"),
    [
        (401, "", "token was not accepted"),
        (403, "", "may not write to that database"),
        (404, "", "no such database"),
        (400, "line 1: bad timestamp", "HTTP 400"),
        (500, "secret internals", "HTTP 500"),
    ],
)
async def test_a_failed_check_names_the_reason_but_not_the_response(
    influx: StubServer,
    store_for_stub: Callable[..., InfluxSink],
    status: int,
    reply: str,
    reason: str,
) -> None:
    """The reason reaches a web page, so the server's own words stay out of it."""
    influx.status, influx.reply = status, reply

    found = await store_for_stub().check()

    assert found is not None and reason in found
    assert "internals" not in found


async def test_a_check_of_an_unreachable_server_says_it_cannot_connect() -> None:
    store = Influx3Sink("http://127.0.0.1:1", "weather")
    try:
        assert await store.check() == "cannot connect (ConnectError)"
    finally:
        await store.aclose()


async def test_a_check_without_a_url_says_so() -> None:
    store = Influx3Sink("", "weather")
    try:
        assert await store.check() == "no database is configured"
    finally:
        await store.aclose()
