"""Notifications through Apprise (extra ``notify``).

One URL list covers email, Signal, Telegram, ntfy, Discord and the rest, so an application needs
no transport configuration of its own. Which events reach whom, and in which words, stays with
the application; this module only delivers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Sender(Protocol):
    """Delivers one message to a set of Apprise URLs."""

    async def send(self, urls: list[str], title: str, body: str) -> bool:
        """Return whether at least one destination accepted the message."""


class AppriseSender:
    """Sends through Apprise.

    Apprise is synchronous and does network IO, so it runs in a worker thread: called directly
    it would block the event loop for as long as the slowest destination takes to answer.
    """

    async def send(self, urls: list[str], title: str, body: str) -> bool:
        """Send to every URL Apprise recognises; False when none is usable or none accepts."""
        return await asyncio.to_thread(self._send, urls, title, body)

    @staticmethod
    def _send(urls: list[str], title: str, body: str) -> bool:
        """The blocking send, run off the event loop."""
        import apprise

        client = apprise.Apprise()
        for url in urls:
            if not client.add(url):
                logger.warning("apprise did not recognise a destination: %s", redact_url(url))
        if not len(client):
            return False
        return bool(client.notify(title=title, body=body))


def redact_url(url: str) -> str:
    """A notification URL with its credentials removed, for logging.

    An Apprise URL is mostly credential -- a bot token, an SMTP password -- so only its scheme
    and last four characters are kept, enough to tell two destinations apart.
    """
    scheme, separator, rest = url.partition("://")
    if not separator:
        return "<malformed url>"
    return f"{scheme}://…" if len(rest) <= 8 else f"{scheme}://…{rest[-4:]}"
