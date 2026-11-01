"""Tell a push monitor that data is arriving (extra ``heartbeat``).

A push monitor -- Uptime Kuma's, healthchecks.io's -- alerts when its URL stops being called.
Calling it after each write a sink accepts makes one monitor cover the whole chain: a source that
stops sending, an unreachable server and a sink that refuses or cannot take writes all stop the
calls alike, while a batch that is merely spooled does not count as delivered.

The calls run on their own task, at most once per interval, so a replayed backlog costs one call
rather than one per batch and a slow monitor never holds up the work. A push URL carries its
monitor's token, so read it from a secret (``HEARTBEAT_URL_FILE``) and never log more than its
host.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx2

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0


class Heartbeat:
    """Calls a URL after each :meth:`beat`, no more often than once per interval.

    ``on_result`` is called with whether each call got through, for a status page to show.
    """

    def __init__(
        self,
        client: httpx2.AsyncClient,
        url: str,
        *,
        interval_seconds: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_result: Callable[[bool], None] = lambda _: None,
    ) -> None:
        self._client = client
        self._url = url
        self._interval = interval_seconds
        self._sleep = sleep
        self._on_result = on_result
        self._due = asyncio.Event()
        self._failing = False

    @property
    def host(self) -> str:
        """Where the calls go, without the path or any credentials in the URL.

        Push URLs carry their monitor's token in the path, and some carry a login, so only the
        host is ever logged.
        """
        return urlsplit(self._url).hostname or "?"

    def beat(self) -> None:
        """Note that data was delivered; the next call goes out as soon as one may."""
        self._due.set()

    async def run(self) -> None:
        """Call the URL for each beat, an interval apart at most. Cancel the task to stop it.

        An unexpected error is logged and the loop carries on: ending it would stop the calls,
        and the monitor would report data missing that is arriving.
        """
        while True:
            await self._due.wait()
            self._due.clear()
            try:
                await self.call()
            except Exception:
                logger.exception("heartbeat to %s failed unexpectedly", self.host)
            await self._sleep(self._interval)

    async def call(self) -> bool:
        """Call the URL once, returning whether the monitor accepted it.

        A failure is logged when calls start failing and again when they recover, not on every
        attempt: the monitor itself raises the alarm, and the log only has to explain it.
        """
        try:
            response = await self._client.get(self._url, timeout=TIMEOUT_SECONDS)
            ok, reason = response.is_success, f"HTTP {response.status_code}"
        except httpx2.RequestError as error:
            ok, reason = False, type(error).__name__
        if not ok and not self._failing:
            logger.warning("heartbeat to %s failed: %s", self.host, reason)
        elif ok and self._failing:
            logger.info("heartbeat to %s is getting through again", self.host)
        self._failing = not ok
        self._on_result(ok)
        return ok
