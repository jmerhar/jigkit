"""InfluxDB sinks: line protocol over HTTP, and how failures classify.

InfluxDB 3 and 2.x take the same line protocol and answer with the same statuses; they differ in
the endpoint, its parameters, how precision is spelt and the token scheme, which is all a
subclass supplies. :class:`Influx3Sink` also answers SQL queries.
"""

from __future__ import annotations

import logging
import math
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2

from jigkit.influx.lineprotocol import encode
from jigkit.sinks import Outcome, Point, Precision

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0
#: A connection test answers a person waiting on a page, and must not let a typed-in address
#: hold a connection open.
CHECK_TIMEOUT_SECONDS = 5.0
#: How much of an error response to keep. InfluxDB explains a rejected write in the body, which
#: is the useful part, but a proxy's HTML error page is not worth a screenful.
ERROR_EXCERPT = 300

#: Client errors that describe the server or the credentials rather than the data. A revoked
#: token or a dropped database is a fault to fix, and the points should still be there once it
#: is: 401 and 403 are authentication, 404 a missing database, 408 and 429 load.
RETRYABLE_CLIENT_ERRORS = frozenset({401, 403, 404, 408, 429})

#: How long the list of tables and their columns is trusted. A field written for the first time
#: is invisible to :meth:`Influx3Sink.table` for at most this long.
COLUMNS_TTL_SECONDS = 300.0

#: A table or field name that may be put into SQL text, quoted.
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*")


def classify(status: int) -> Outcome:
    """The outcome an HTTP status means for a write."""
    if 200 <= status < 300:
        return Outcome.OK
    if status in RETRYABLE_CLIENT_ERRORS or status >= 500:
        return Outcome.RETRY
    return Outcome.REJECT


class InfluxSink(ABC):
    """Writes line protocol to one InfluxDB database."""

    def __init__(
        self,
        url: str,
        database: str,
        token: str = "",
        *,
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.database = database
        self.token = token
        self._client = client or httpx2.AsyncClient(timeout=TIMEOUT_SECONDS)
        self.last_error: str | None = None

    @property
    def configured(self) -> bool:
        """Whether there is anywhere to write to."""
        return bool(self.url)

    async def write(self, points: list[Point]) -> Outcome:
        """Write points once as line protocol, returning what became of them.

        Failures are logged and reported rather than raised, so a caller's own work never waits
        on, or depends on, the database.
        """
        payload, precision = encode(points)
        if not payload:
            return Outcome.OK
        if not self.configured:
            return self._fail(Outcome.RETRY, "no database is configured")
        try:
            response = await self._post(payload, precision)
        except httpx2.RequestError as error:
            return self._fail(Outcome.RETRY, f"{type(error).__name__}: {error}")
        outcome = classify(response.status_code)
        if outcome is not Outcome.OK:
            detail = f"HTTP {response.status_code}: {response.text[:ERROR_EXCERPT]}"
            return self._fail(outcome, detail)
        self.last_error = None
        return Outcome.OK

    async def check(self) -> str | None:
        """Whether a write would be accepted, found by sending an empty one.

        InfluxDB checks the token and the database before it looks at the body, so an empty
        write is refused for being empty only when everything else is right. Nothing is written.
        The answer names only the status, never the response body.
        """
        if not self.configured:
            return "no database is configured"
        try:
            response = await self._post("", Precision.SECONDS, timeout=CHECK_TIMEOUT_SECONDS)
        except httpx2.RequestError as error:
            return f"cannot connect ({type(error).__name__})"
        status = response.status_code
        if 200 <= status < 300 or (status == 400 and "empty" in response.text.lower()):
            return None
        reasons = {
            401: "the token was not accepted",
            403: "the token may not write to that database",
            404: "no such database",
        }
        return reasons.get(status, f"InfluxDB answered HTTP {status}")

    async def flush(self) -> None:  # noqa: B027 -- concrete: there is never anything held back
        """Nothing to send: every write goes out when it is made."""

    async def aclose(self) -> None:
        """Release the HTTP client's connections."""
        await self._client.aclose()

    async def _post(
        self, payload: str, precision: Precision, timeout: float = TIMEOUT_SECONDS
    ) -> httpx2.Response:
        """POST line protocol to this version's write endpoint."""
        path, params, scheme = self._write_endpoint(precision)
        headers = {"Content-Type": "text/plain; charset=utf-8"}
        if self.token:
            headers["Authorization"] = f"{scheme} {self.token}"
        return await self._client.post(
            self.url + path,
            params=params,
            headers=headers,
            content=payload.encode("utf-8"),
            timeout=timeout,
        )

    @abstractmethod
    def _write_endpoint(self, precision: Precision) -> tuple[str, dict[str, str], str]:
        """The write path, its query parameters, and the Authorization scheme."""

    def _fail(self, outcome: Outcome, reason: str) -> Outcome:
        """Record and log a failed write."""
        self.last_error = reason
        verdict = "will retry" if outcome is Outcome.RETRY else "refused, not retrying"
        logger.error("write to InfluxDB failed (%s): %s", verdict, reason)
        return outcome


class Influx2Sink(InfluxSink):
    """Writes to an InfluxDB 2.x bucket, which belongs to an organisation."""

    def __init__(
        self,
        url: str,
        database: str,
        token: str = "",
        *,
        org: str = "",
        client: httpx2.AsyncClient | None = None,
    ) -> None:
        super().__init__(url, database, token, client=client)
        self.org = org

    def _write_endpoint(self, precision: Precision) -> tuple[str, dict[str, str], str]:
        """``/api/v2/write`` with the ``Token`` scheme; precision is spelt ``s``, ``ms`` ..."""
        params = {"bucket": self.database, "org": self.org, "precision": precision.value}
        return "/api/v2/write", params, "Token"


class QueryError(Exception):
    """The database could not answer: unreachable, refusing the token, or failing the query."""


class TableNotFound(QueryError):
    """The query named a table the database does not have."""


@dataclass(frozen=True)
class TableInfo:
    """A table's columns, and which of them are tags."""

    columns: frozenset[str] = frozenset()
    tags: tuple[str, ...] = ()


#: How InfluxDB 3 spells each precision on its write endpoint.
_V3_PRECISION = {
    Precision.SECONDS: "second",
    Precision.MILLISECONDS: "millisecond",
    Precision.MICROSECONDS: "microsecond",
    Precision.NANOSECONDS: "nanosecond",
}


class Influx3Sink(InfluxSink):
    """Writes to, and reads from, an InfluxDB 3 database.

    Table and field names in a query come from the caller, so put them into SQL only after
    checking them against :meth:`table` and :data:`IDENTIFIER`, quoted; values travel as query
    parameters, never inside the SQL text.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tables: dict[str, TableInfo] = {}
        self._columns_at = -math.inf

    def _write_endpoint(self, precision: Precision) -> tuple[str, dict[str, str], str]:
        """``/api/v3/write_lp`` with a bearer token; precision is spelt ``second`` ..."""
        params = {"db": self.database, "precision": _V3_PRECISION[precision]}
        return "/api/v3/write_lp", params, "Bearer"

    async def check_read(self) -> str | None:
        """Whether a query would be answered, found by running a trivial one."""
        if not self.configured:
            return "no database is configured"
        try:
            await self.query("SELECT 1", timeout=CHECK_TIMEOUT_SECONDS)
        except QueryError as error:
            return str(error)
        return None

    async def table(self, name: str) -> TableInfo:
        """The columns of table ``name``, none if it does not exist; cached briefly.

        InfluxDB 3 stores tags as dictionary-encoded strings, which is how they are told apart
        from fields.
        """
        if not IDENTIFIER.fullmatch(name):
            raise ValueError(f"not a table name: {name!r}")
        now = time.monotonic()
        if now - self._columns_at > COLUMNS_TTL_SECONDS:
            rows = await self.rows(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'iox'"
            )
            columns: dict[str, set[str]] = {}
            tags: dict[str, list[str]] = {}
            for row in rows:
                columns.setdefault(row["table_name"], set()).add(row["column_name"])
                if str(row.get("data_type", "")).startswith("Dictionary"):
                    tags.setdefault(row["table_name"], []).append(row["column_name"])
            self._tables = {
                table: TableInfo(frozenset(names), tuple(tags.get(table, ())))
                for table, names in columns.items()
            }
            self._columns_at = now
        return self._tables.get(name, TableInfo())

    async def rows(self, sql: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """The rows a query returns, or none if it names a table that does not exist."""
        try:
            return await self.query(sql, params)
        except TableNotFound:
            return []

    async def query(
        self, sql: str, params: dict[str, str] | None = None, *, timeout: float | None = None
    ) -> list[dict[str, Any]]:
        """Run one SQL query, returning its rows as dicts with null columns left out.

        Raises :class:`TableNotFound` for a table the database does not have, and
        :class:`QueryError` for any other failure.
        """
        if not self.configured:
            raise QueryError("no database is configured")
        body: dict[str, object] = {"db": self.database, "q": sql, "format": "json"}
        if params:
            body["params"] = params
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = await self._client.post(
                self.url + "/api/v3/query_sql",
                json=body,
                headers=headers,
                timeout=timeout or TIMEOUT_SECONDS,
            )
        except httpx2.RequestError as error:
            raise QueryError(f"cannot connect ({type(error).__name__})") from error
        status = response.status_code
        if status == 200:
            rows = response.json()
            if not isinstance(rows, list):
                raise QueryError("InfluxDB answered with something other than rows")
            return rows
        text = response.text[:ERROR_EXCERPT]
        if status == 400 and re.search(r"table '[^']*' not found", text):
            raise TableNotFound(text)
        logger.error("query to InfluxDB failed: HTTP %s: %s", status, text)
        reasons = {
            401: "the token was not accepted",
            403: "the token may not read that database",
            404: "no such database",
        }
        raise QueryError(reasons.get(status, f"InfluxDB answered HTTP {status}"))


def sql_timestamp(moment: datetime) -> str:
    """A SQL timestamp literal for an aware datetime, in UTC to the second."""
    if moment.tzinfo is None:
        raise ValueError("a query's times must carry a time zone")
    return f"TIMESTAMP '{moment.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}'"


def parse_time(text: str) -> datetime:
    """A UTC datetime from InfluxDB's timestamps, which have no zone and up to nanoseconds."""
    whole, _, fraction = text.partition(".")
    moment = datetime.fromisoformat(whole).replace(tzinfo=UTC)
    if fraction:
        moment += timedelta(microseconds=int(fraction[:6].ljust(6, "0")))
    return moment
