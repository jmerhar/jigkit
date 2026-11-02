"""Password hashes: Argon2id at the library's defaults, and a length floor."""

from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

#: The shortest password :func:`hash_password` accepts unless told otherwise.
MIN_PASSWORD_LENGTH = 10

# The library's defaults are memory-hard, and move with the library rather than with a number
# pinned here that nobody revisits.
_hasher = PasswordHasher()


class PasswordTooShort(ValueError):
    """A new password is shorter than the minimum."""


def hash_password(password: str, *, min_length: int = MIN_PASSWORD_LENGTH) -> str:
    """An Argon2id hash of ``password``, which must be at least ``min_length`` characters.

    A length floor is the one rule enforced in code: an application reachable from the internet
    has a short password as its whole attack surface.
    """
    if len(password) < min_length:
        raise PasswordTooShort(f"a password needs at least {min_length} characters")
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Whether ``password`` matches the hash; a malformed hash simply does not match."""
    try:
        return _hasher.verify(password_hash, password)
    except Argon2Error, InvalidHashError:
        return False


#: Verified against when a login names nobody, so an unknown login takes as long to refuse as a
#: wrong password and timing does not reveal which logins exist.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    """Spend the time a real password check takes, for a login that names nobody."""
    verify_password(_DUMMY_HASH, password)
