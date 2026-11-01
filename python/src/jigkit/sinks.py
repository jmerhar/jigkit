"""Points, the outcome of writing them, and the interface every destination implements.

A sink is anywhere points go: an InfluxDB database (``jigkit.influx``), or any other store an
application adds. Sources produce :class:`Point` s, each stamped with the time it was measured at
its source and that time's precision; a sink encodes them in its own wire format when it writes.

While a write cannot happen, points wait on disk (``jigkit.spool``) in the neutral text form
:func:`dump_points` produces, so a backlog survives its sink being reconfigured, replaced, or
changed to another kind before it drains.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

#: A field's value. A float is a measurement, an int a code or count, a bool a state.
FieldValue = float | int | bool | str


class Precision(Enum):
    """The unit a point's timestamp counts in, by its short name."""

    SECONDS = "s"
    MILLISECONDS = "ms"
    MICROSECONDS = "us"
    NANOSECONDS = "ns"

    @property
    def per_second(self) -> int:
        """How many of this unit make a second."""
        return {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}[self.value]


@dataclass(frozen=True)
class Point:
    """One point: a table, its tags, its fields, and when it was measured.

    The timestamp is an integer count of ``precision`` units since the Unix epoch, always set by
    whoever measured the point; a sink never lets the server stamp it on arrival, which would
    record when a backlog was replayed rather than when the value was true.
    """

    table: str
    tags: tuple[tuple[str, str], ...]
    timestamp: int
    fields: dict[str, FieldValue] = field(default_factory=dict)
    precision: Precision = field(kw_only=True)

    def timestamp_in(self, precision: Precision) -> int:
        """The timestamp in another unit; converting to a coarser one truncates."""
        if precision is self.precision:
            return self.timestamp
        return self.timestamp * precision.per_second // self.precision.per_second


class Outcome(Enum):
    """What became of one attempt to write."""

    #: Stored.
    OK = "ok"
    #: Not stored, and worth trying again: the sink is unreachable, overloaded, or refusing this
    #: client for a reason someone can fix.
    RETRY = "retry"
    #: Not stored, and never will be: the sink refused the data itself. Retrying would block
    #: every write queued behind this one.
    REJECT = "reject"


class Sink(Protocol):
    """A destination points are written to."""

    #: Why the last write failed, or None after a success.
    last_error: str | None

    @property
    def configured(self) -> bool:
        """Whether there is anywhere to write to."""

    async def write(self, points: list[Point]) -> Outcome:
        """Write points once, returning what became of them. Never raises for a failed write."""

    async def check(self) -> str | None:
        """Whether this sink would accept a write, without writing: None, or the reason not."""

    async def flush(self) -> None:
        """Send anything the sink is holding back; a sink that buffers nothing does nothing."""

    async def aclose(self) -> None:
        """Release connections."""


def dump_points(points: list[Point]) -> str:
    """Points as text any sink can be given later: one JSON array, field types preserved.

    JSON keeps the distinctions between ``60.0``, ``60`` and ``true``, so nothing changes type on
    the way through: a measurement stays a float and a code an integer.
    """
    return json.dumps(
        [
            [p.table, [list(tag) for tag in p.tags], p.timestamp, p.fields, p.precision.value]
            for p in points
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def load_points(text: str) -> list[Point]:
    """Points from :func:`dump_points`' text. Raises ValueError for anything else.

    An entry without a precision, in the four-element form, counts in seconds.
    """
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            raise TypeError(f"a {type(data).__name__}, not a list")
        points = []
        for entry in data:
            table, tags, timestamp, fields, *rest = entry
            if len(rest) > 1:
                raise ValueError(f"an entry of {len(entry)} elements")
            precision = Precision(rest[0]) if rest else Precision.SECONDS
            points.append(
                Point(
                    table,
                    tuple((k, v) for k, v in tags),
                    timestamp,
                    dict(fields),
                    precision=precision,
                )
            )
        return points
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError(f"not a list of points: {error}") from error
