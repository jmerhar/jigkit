"""Logging people in (extra ``auth``): passwords, the login throttle, cookies, first-run setup.

Database sessions are in :mod:`jigkit.auth.sessions`, which also needs the ``db`` extra.
"""

from jigkit.auth.cookies import clear_session_cookie, cookie_secure, issue_session_cookie
from jigkit.auth.passwords import (
    MIN_PASSWORD_LENGTH,
    PasswordTooShort,
    burn_password_check,
    hash_password,
    verify_password,
)
from jigkit.auth.setup import SETUP_TOKEN_DISABLED, resolve_setup_token, setup_token_matches
from jigkit.auth.throttle import LoginThrottle

__all__ = [
    "MIN_PASSWORD_LENGTH",
    "SETUP_TOKEN_DISABLED",
    "LoginThrottle",
    "PasswordTooShort",
    "burn_password_check",
    "clear_session_cookie",
    "cookie_secure",
    "hash_password",
    "issue_session_cookie",
    "resolve_setup_token",
    "setup_token_matches",
    "verify_password",
]
