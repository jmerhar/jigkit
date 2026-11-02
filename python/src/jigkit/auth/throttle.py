"""Slowing down a run of guessed passwords."""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from collections.abc import Callable

#: How far back failures count, in seconds.
WINDOW_SECONDS = 60.0


class LoginThrottle:
    """Failed logins per client address in a sliding minute; past the limit, logins are refused.

    Only failures count, so a person who logs in, out and in again is never refused; a success
    forgets the address's failures. Addresses are kept in least-recently-used order and the
    oldest is forgotten beyond ``max_clients``, so a run of logins from many addresses cannot grow
    it without bound. In memory: a restart forgets it, which gives an attacker nothing waiting a
    minute would not.

    The address must be the client's own. Behind a reverse proxy that takes uvicorn believing the
    proxy's X-Forwarded-For (``FORWARDED_ALLOW_IPS``); otherwise every client shares the proxy's
    address, and one person's failures lock everyone out.
    """

    def __init__(
        self,
        per_minute: int,
        *,
        max_clients: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.per_minute = per_minute
        self.max_clients = max_clients
        self._clock = clock
        self._failures: OrderedDict[str, deque[float]] = OrderedDict()

    def _recent(self, address: str) -> deque[float] | None:
        """The address's failures within the window, without adding the address."""
        window = self._failures.get(address)
        if window is None:
            return None
        cutoff = self._clock() - WINDOW_SECONDS
        while window and window[0] <= cutoff:
            window.popleft()
        if not window:
            del self._failures[address]
            return None
        return window

    def blocked(self, address: str) -> bool:
        """Whether ``address`` has used up its failed attempts for now."""
        window = self._recent(address)
        return window is not None and len(window) >= self.per_minute

    def failed(self, address: str) -> None:
        """Count a failed login from ``address``."""
        window = self._recent(address)
        if window is None:
            window = self._failures[address] = deque()
        else:
            self._failures.move_to_end(address)
        window.append(self._clock())
        while len(self._failures) > self.max_clients:
            self._failures.popitem(last=False)

    def succeeded(self, address: str) -> None:
        """Forget ``address``'s failures after it logs in."""
        self._failures.pop(address, None)
