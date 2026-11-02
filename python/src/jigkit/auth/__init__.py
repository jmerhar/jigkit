"""Logging people in (extra ``auth``): passwords, the login throttle and the session cookie.

Database sessions are in :mod:`jigkit.auth.sessions`, which also needs the ``db`` extra, and
passkeys in :mod:`jigkit.auth.passkeys`, which needs the ``passkeys`` and ``db`` extras.
"""

from jigkit.auth.cookies import clear_session_cookie, cookie_secure, issue_session_cookie
from jigkit.auth.passwords import (
    MIN_PASSWORD_LENGTH,
    PasswordTooShort,
    burn_password_check,
    hash_password,
    verify_password,
)
from jigkit.auth.throttle import LoginThrottle

__all__ = [
    "MIN_PASSWORD_LENGTH",
    "LoginThrottle",
    "PasswordTooShort",
    "burn_password_check",
    "clear_session_cookie",
    "cookie_secure",
    "hash_password",
    "issue_session_cookie",
    "verify_password",
]
