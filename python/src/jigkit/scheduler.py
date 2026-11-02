"""Work an application does on its own, on a fixed tick, inside its own process.

A plain asyncio loop rather than a scheduling library: an application's scheduled work is "do
whatever is due", with what is due kept in its own data, and a tick that is a method call can be
driven directly by a test instead of waited for.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class TickLoop:
    """Calls ``tick`` every ``interval_seconds`` between :meth:`start` and :meth:`stop`.

    A tick that raises is logged and the loop carries on: a loop that died on one bad tick would
    stop every later piece of work without saying so. ``enabled=False`` makes :meth:`start` do
    nothing, which is how tests drive ``tick`` themselves.
    """

    def __init__(
        self,
        tick: Callable[[], Awaitable[None]],
        interval_seconds: float,
        *,
        enabled: bool = True,
        name: str = "scheduler",
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._tick = tick
        self._interval = interval_seconds
        self._enabled = enabled
        self._name = name
        self._sleep = sleep
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        """Whether the loop has been started and not stopped."""
        return self._task is not None

    def start(self) -> None:
        """Begin ticking, unless disabled or already started."""
        if not self._enabled:
            logger.info("%s disabled by configuration", self._name)
            return
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop(), name=self._name)
        logger.info("%s started, ticking every %gs", self._name, self._interval)

    async def stop(self) -> None:
        """Stop ticking and wait for the loop to unwind."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        """Tick, then wait, for ever."""
        while True:
            try:
                await self._tick()
            except Exception:
                logger.exception("%s tick failed; the next one tries again", self._name)
            await self._sleep(self._interval)
