"""Reading back from InfluxDB 3 with SQL, against a real HTTP server answering each query."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from jigkit.influx import sink as influx_sink
from jigkit.influx.sink import (
    Influx3Sink,
    QueryError,
    TableInfo,
    TableNotFound,
    parse_time,
    sql_timestamp,
)
from jigkit.testing.http import Received, StubServer

#: Columns by table; tags are upper-case here, and reported as InfluxDB reports tags.
COLUMNS = {
    "meter": ["time", "DEVICE", "PHASE", "power_w", "energy_kwh"],
    "price": ["time", "eur_kwh"],
}


class Database:
    """Answers the catalogue query from COLUMNS and every other query with ``rows``."""

    def __init__(self) -> None:
        self.rows: Any = []
        self.status = 200
        self.error = ""
        self.queries: list[dict[str, Any]] = []

    def __call__(self, request: Received) -> tuple[int, str]:
        body = json.loads(request.body)
        if "information_schema" in body["q"]:
            columns = [
                {
                    "table_name": table,
                    "column_name": column.lower(),
                    "data_type": "Dictionary(Int32, Utf8)" if column.isupper() else "Float64",
                }
                for table, names in COLUMNS.items()
                for column in names
            ]
            return 200, json.dumps(columns)
        self.queries.append(body)
        if self.status != 200:
            return self.status, self.error
        return 200, json.dumps(self.rows)


@pytest.fixture
def db(influx: StubServer) -> Database:
    database = Database()
    influx.respond = database
    return database


@pytest.fixture
async def reader(influx: StubServer, db: Database) -> AsyncIterator[Influx3Sink]:
    store = Influx3Sink(influx.url, "energy", "apiv3_read")
    yield store
    await store.aclose()


async def test_a_query_goes_to_query_sql_with_the_token_and_parameters(
    reader: Influx3Sink, influx: StubServer, db: Database
) -> None:
    db.rows = [{"time": "2026-11-01T00:00:00", "power_w": 120.5}]

    rows = await reader.query("SELECT * FROM meter WHERE device = $device", {"device": "plug"})

    assert rows == db.rows
    request = influx.requests[-1]
    assert request.path == "/api/v3/query_sql"
    assert request.headers["authorization"] == "Bearer apiv3_read"
    assert db.queries[-1] == {
        "db": "energy",
        "q": "SELECT * FROM meter WHERE device = $device",
        "format": "json",
        "params": {"device": "plug"},
    }


async def test_a_query_without_parameters_sends_none(reader: Influx3Sink, db: Database) -> None:
    await reader.query("SELECT 1")

    assert "params" not in db.queries[-1]


async def test_a_missing_table_is_its_own_error_and_reads_as_no_rows(
    reader: Influx3Sink, db: Database
) -> None:
    db.status, db.error = 400, "Error during planning: table 'iox.nothing' not found"

    with pytest.raises(TableNotFound):
        await reader.query("SELECT * FROM nothing")
    assert await reader.rows("SELECT * FROM nothing") == []


async def test_the_catalogue_tells_tags_from_fields(reader: Influx3Sink) -> None:
    assert await reader.table("meter") == TableInfo(
        frozenset({"time", "device", "phase", "power_w", "energy_kwh"}), ("device", "phase")
    )
    assert await reader.table("absent") == TableInfo()


async def test_anything_but_a_table_name_is_refused(reader: Influx3Sink) -> None:
    with pytest.raises(ValueError, match="not a table name"):
        await reader.table('meter"; DROP')


async def test_the_catalogue_is_cached(
    reader: Influx3Sink, influx: StubServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    await reader.table("meter")
    await reader.table("price")
    assert len([r for r in influx.requests if "information_schema" in r.body]) == 1

    monkeypatch.setattr(influx_sink, "COLUMNS_TTL_SECONDS", -1.0)
    await reader.table("meter")
    assert len([r for r in influx.requests if "information_schema" in r.body]) == 2


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (401, "the token was not accepted"),
        (403, "the token may not read that database"),
        (404, "no such database"),
        (500, "InfluxDB answered HTTP 500"),
        (400, "InfluxDB answered HTTP 400"),
    ],
)
async def test_a_failed_query_raises_with_the_reason(
    reader: Influx3Sink, db: Database, status: int, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    db.status, db.error = status, "Schema error: internals"

    with caplog.at_level(logging.ERROR), pytest.raises(QueryError) as raised:
        await reader.query("SELECT * FROM meter")

    assert str(raised.value) == reason
    assert "internals" in caplog.text, "the body is logged for the operator"
    assert await reader.check_read() == reason


async def test_an_answer_that_is_not_rows_is_an_error(reader: Influx3Sink, db: Database) -> None:
    db.rows = {"error": "no"}

    with pytest.raises(QueryError, match="other than rows"):
        await reader.query("SELECT 1")


async def test_a_check_runs_a_trivial_query(reader: Influx3Sink, db: Database) -> None:
    db.rows = [{"Int64(1)": 1}]

    assert await reader.check_read() is None
    assert db.queries[-1]["q"] == "SELECT 1"


async def test_an_unreachable_server_cannot_be_read() -> None:
    store = Influx3Sink("http://127.0.0.1:1", "energy")
    try:
        assert await store.check_read() == "cannot connect (ConnectError)"
        with pytest.raises(QueryError):
            await store.query("SELECT 1")
    finally:
        await store.aclose()


async def test_without_a_url_nothing_is_read() -> None:
    store = Influx3Sink("", "energy")
    try:
        assert await store.check_read() == "no database is configured"
        with pytest.raises(QueryError, match="no database"):
            await store.query("SELECT 1")
    finally:
        await store.aclose()


async def test_no_token_sends_no_authorization(influx: StubServer, db: Database) -> None:
    store = Influx3Sink(influx.url, "energy")
    try:
        await store.query("SELECT 1")
    finally:
        await store.aclose()

    assert "authorization" not in influx.requests[-1].headers


class TestTimes:
    def test_sql_timestamp_is_utc_to_the_second(self) -> None:
        moment = datetime(2026, 11, 1, 13, 30, 15, 999, tzinfo=timezone(timedelta(hours=1)))

        assert sql_timestamp(moment) == "TIMESTAMP '2026-11-01T12:30:15Z'"

    def test_sql_timestamp_refuses_a_naive_time(self) -> None:
        with pytest.raises(ValueError, match="time zone"):
            sql_timestamp(datetime(2026, 11, 1))

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("2026-11-01T12:30:15", datetime(2026, 11, 1, 12, 30, 15, tzinfo=UTC)),
            (
                "2026-11-01T12:30:15.123456789",
                datetime(2026, 11, 1, 12, 30, 15, 123456, tzinfo=UTC),
            ),
            ("2026-11-01T12:30:15.5", datetime(2026, 11, 1, 12, 30, 15, 500000, tzinfo=UTC)),
        ],
    )
    def test_parse_time(self, text: str, expected: datetime) -> None:
        assert parse_time(text) == expected
