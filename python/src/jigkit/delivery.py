"""Getting points into a sink eventually: write now if possible, spool and replay if not.

A batch is written straight away while nothing is waiting. Once anything is, new batches join the
end of the queue instead, and one background loop drains it oldest first with growing pauses
between failed attempts -- so an outage costs one retry per pause rather than one per batch, and
the backlog lands in the order it arrived.

One :class:`Delivery` serves one sink with its own :class:`~jigkit.spool.Spool`; an application
writing to several destinations runs one per destination, so a failing destination holds back
only its own backlog.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from jigkit.sinks import Outcome, Point, dump_points, load_points
from jigkit.spool import Spool

logger = logging.getLogger(__name__)

FIRST_PAUSE_SECONDS = 1.0
MAX_PAUSE_SECONDS = 60.0


class Writer(Protocol):
    """Something that attempts one write and says what became of it -- a sink, in practice."""

    async def write(self, points: list[Point]) -> Outcome:
        """Write points once."""


class DeliveryEvents(Protocol):
    """What a delivery reports as it works, for an application's status page to count."""

    def record_write(self, ok: bool) -> None:
        """A write was attempted; ``ok`` says whether the sink accepted it."""

    def record_spooled(self) -> None:
        """A batch was queued to be written later."""

    def record_rejected_write(self) -> None:
        """The sink refused a batch for good."""


class _NoEvents:
    """The events of an application that counts nothing."""

    def record_write(self, ok: bool) -> None:
        """Ignore a write."""

    def record_spooled(self) -> None:
        """Ignore a spooled batch."""

    def record_rejected_write(self) -> None:
        """Ignore a rejected batch."""


class Delivery:
    """Writes batches, spooling the ones that cannot be written yet.

    ``on_written`` is called with the points of every write the sink accepts, live or replayed.
    """

    def __init__(
        self,
        sink: Writer,
        spool: Spool,
        *,
        events: DeliveryEvents | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_written: Callable[[list[Point]], None] = lambda _: None,
    ) -> None:
        self._sink = sink
        self._spool = spool
        self._events = events or _NoEvents()
        self._sleep = sleep
        self._on_written = on_written
        self._wake = asyncio.Event()

    async def submit(self, points: list[Point]) -> None:
        """Deliver one batch now, or queue it for the replay loop."""
        if not points:
            return
        if len(self._spool):
            self._queue(points)
            return
        outcome = await self._sink.write(points)
        self._events.record_write(outcome is Outcome.OK)
        if outcome is Outcome.OK:
            self._on_written(points)
        elif outcome is Outcome.RETRY:
            self._queue(points)
        else:
            self._events.record_rejected_write()
            self._spool.quarantine_body(dump_points(points))

    async def run(self) -> None:
        """Replay spooled batches for ever, oldest first. Cancel the task to stop it.

        An unexpected error is logged and waited out like a failed write, never allowed to end
        the loop: with it gone, every later batch would queue with nothing to drain it.
        """
        pause = FIRST_PAUSE_SECONDS
        while True:
            try:
                pause = await self._step(pause)
            except Exception:
                logger.exception("replaying the spool failed; trying again in %.0f s", pause)
                await self._sleep(pause)
                pause = min(pause * 2, MAX_PAUSE_SECONDS)

    async def _step(self, pause: float) -> float:
        """Replay the oldest batch, or wait for one; return the pause the next failure takes."""
        path = self._spool.oldest()
        if path is None:
            self._wake.clear()
            await self._wake.wait()
            return FIRST_PAUSE_SECONDS
        try:
            points = load_points(self._spool.read(path))
        except OSError, UnicodeDecodeError:
            logger.exception("cannot read spooled batch %s; setting it aside", path.name)
            self._spool.quarantine(path)
            return pause
        except ValueError:
            # Not points -- a format an older version spooled, or a file edited by hand -- so no
            # sink can be given it.
            logger.error("spooled batch %s is not points; setting it aside", path.name)
            self._spool.quarantine(path)
            return pause

        outcome = await self._sink.write(points)
        self._events.record_write(outcome is Outcome.OK)
        if outcome is Outcome.OK:
            self._spool.ack(path)
            self._on_written(points)
            pause = FIRST_PAUSE_SECONDS
            if not len(self._spool):
                logger.info("spool drained")
        elif outcome is Outcome.REJECT:
            self._events.record_rejected_write()
            self._spool.quarantine(path)
        else:
            await self._sleep(pause)
            pause = min(pause * 2, MAX_PAUSE_SECONDS)
        return pause

    def _queue(self, points: list[Point]) -> None:
        """Add a batch to the spool and wake the replay loop."""
        if self._spool.enqueue(dump_points(points)):
            self._events.record_spooled()
        self._wake.set()
