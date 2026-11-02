"""First-run setup: the token that guards creating the first administrator."""

from __future__ import annotations

import hmac
import secrets

#: The value that turns the setup token off, for an instance nobody else can reach.
SETUP_TOKEN_DISABLED = "off"


def resolve_setup_token(configured: str | None) -> str | None:
    """The token the first-run setup will ask for, or None when it is switched off.

    Generated when none is configured, so an instance reachable from the internet before anyone
    has set it up cannot be claimed by whoever finds its address first. Log a generated token
    where the operator will see it; it is needed once, and never after setup.
    """
    if configured == SETUP_TOKEN_DISABLED:
        return None
    return configured or secrets.token_urlsafe(9)


def setup_token_matches(expected: str | None, given: str | None) -> bool:
    """Whether ``given`` is the setup token, compared in constant time.

    With the token switched off (``expected`` None) anything matches. Compared as UTF-8 bytes, so
    a token with non-ASCII characters is refused rather than raising.
    """
    if expected is None:
        return True
    if given is None:
        return False
    return hmac.compare_digest(expected.encode(), given.encode())
