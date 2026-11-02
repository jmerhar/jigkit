"""A stand-in for :class:`jigkit.notify.Sender` that records what it was asked to send."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Sent:
    """One message a :class:`RecordingSender` was given."""

    urls: list[str]
    title: str
    body: str


@dataclass
class RecordingSender:
    """Keeps every message instead of sending it, and answers with ``accept``."""

    accept: bool = True
    sent: list[Sent] = field(default_factory=list)

    async def send(self, urls: list[str], title: str, body: str) -> bool:
        """Record the message and return ``accept``."""
        self.sent.append(Sent(list(urls), title, body))
        return self.accept
