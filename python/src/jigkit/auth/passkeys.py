"""Passkeys (extras ``passkeys`` and ``db``): adding one to an account, and logging in with one.

A WebAuthn ceremony is two requests. The server hands out options carrying a fresh challenge;
the browser passes them to an authenticator and comes back with its answer. Between the two, the
challenge waits in :class:`Ceremonies`, in memory, under a random key the browser holds in a
short-lived cookie (:func:`hold_ceremony`). The functions here wrap the ``webauthn`` library so
that an application's routes deal only in JSON, bytes and :class:`PasskeyRejected`::

    class Passkey(PasskeyMixin, Base):
        __tablename__ = "passkey"
        person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))

Registration: :func:`registration_options`, then :func:`verify_registration`, which returns the
:class:`NewPasskey` to store. Logging in: :func:`authentication_options`, then
:func:`parse_login` to learn which passkey answered, then :func:`verify_login` against it, which
returns the signature counter to store.

Passkeys are discoverable, so a login names nobody up front: the authenticator offers whichever
of its passkeys belong to the site, and the answer says which one it used.
"""

from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from sqlalchemy import JSON, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import parse_authentication_credential_json
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from jigkit.auth.cookies import cookie_secure
from jigkit.models import UtcDateTime, utcnow

if TYPE_CHECKING:
    from fastapi import Request, Response

#: How long a ceremony may take between its two requests.
CEREMONY_SECONDS = 300
#: The most ceremonies kept waiting at once; beyond it the oldest are forgotten, so requests
#: that start ceremonies and never finish them cannot grow the process without bound.
MAX_CEREMONIES = 10_000
#: The longest label a person can give a passkey.
LABEL_LENGTH = 100

#: What parsing and verifying raise for an answer that does not hold up: the library's own
#: failures, and malformed base64 in a field it decodes without wrapping the error.
_REJECTED = (WebAuthnException, ValueError)


class PasskeyRejected(Exception):
    """An authenticator's answer that is malformed or does not verify."""


@dataclass(frozen=True)
class Party:
    """Who passkeys belong to: the site's host name, and the origin answers must come from."""

    rp_id: str
    origin: str


def relying_party(public_url: str | None, scheme: str, host: str) -> Party:
    """The relying party for a request: the configured public URL's, else the request's own.

    A passkey is bound to the host name it was made for, so a deployment behind a proxy needs its
    public URL set for passkeys made there to keep working. ``host`` is the request's Host
    header, port included.
    """
    if public_url:
        parts = urlsplit(public_url)
        return Party(rp_id=parts.hostname or "", origin=f"{parts.scheme}://{parts.netloc}")
    return Party(rp_id=urlsplit(f"//{host}").hostname or "", origin=f"{scheme}://{host}")


def request_party(request: Request, public_url: str | None) -> Party:
    """:func:`relying_party` for a FastAPI request."""
    return relying_party(public_url, request.url.scheme, request.headers.get("host", ""))


@dataclass(frozen=True)
class Ceremony:
    """A challenge handed out, and whose ceremony it is: None for a login, which names nobody."""

    challenge: bytes
    owner_id: int | None
    expires: float


class Ceremonies:
    """Challenges waiting for their answer. Each is used once; an expired one is forgotten.

    Held in memory, so a ceremony in flight across a restart has to be started again, and an
    application running several processes needs its ceremony requests to reach the same one.
    """

    def __init__(
        self,
        *,
        lifetime_seconds: float = CEREMONY_SECONDS,
        max_waiting: int = MAX_CEREMONIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._lifetime = lifetime_seconds
        self._max_waiting = max_waiting
        self._clock = clock
        self._waiting: dict[str, Ceremony] = {}

    def __len__(self) -> int:
        return len(self._waiting)

    def start(self, challenge: bytes, owner_id: int | None) -> str:
        """Keep a challenge for its answer, and return the key the browser holds."""
        self._forget_expired()
        while len(self._waiting) >= self._max_waiting:
            del self._waiting[next(iter(self._waiting))]
        key = secrets.token_urlsafe(24)
        self._waiting[key] = Ceremony(challenge, owner_id, self._clock() + self._lifetime)
        return key

    def finish(self, key: str | None) -> Ceremony | None:
        """The ceremony a key belongs to, if it is still waiting; it can be finished only once."""
        self._forget_expired()
        return self._waiting.pop(key, None) if key else None

    def _forget_expired(self) -> None:
        """Drop every ceremony past its expiry; they are kept in the order they expire."""
        now = self._clock()
        while self._waiting:
            key = next(iter(self._waiting))
            if self._waiting[key].expires > now:
                return
            del self._waiting[key]


def hold_ceremony(
    response: Response,
    request: Request,
    key: str,
    *,
    name: str,
    path: str = "/",
    max_age_seconds: int = CEREMONY_SECONDS,
    secure: bool | None = None,
) -> None:
    """Give the browser a ceremony's key, for the request that finishes it.

    HttpOnly and SameSite=Strict: the ceremony is finished by the application's own page, so the
    cookie never needs to travel with a request from anywhere else. ``path`` can narrow it to the
    routes that finish ceremonies.
    """
    response.set_cookie(
        name,
        key,
        max_age=max_age_seconds,
        httponly=True,
        samesite="strict",
        secure=cookie_secure(request, secure),
        path=path,
    )


def clear_ceremony(response: Response, *, name: str, path: str = "/") -> None:
    """Remove a finished ceremony's key from the browser."""
    response.delete_cookie(name, path=path, httponly=True, samesite="strict")


class PasskeyMixin:
    """The columns of a passkey table; the application adds the owner's foreign key."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    credential_id: Mapped[bytes] = mapped_column(LargeBinary(1024), unique=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary(2048))
    #: The authenticator's signature counter; one that goes backwards betrays a cloned key.
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    transports: Mapped[list[str]] = mapped_column(JSON, default=list)
    label: Mapped[str] = mapped_column(String(LABEL_LENGTH))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


@dataclass(frozen=True)
class Options:
    """What a ceremony's first request returns: the options as the browser's API takes them, and
    the challenge in them, for :class:`Ceremonies` to keep."""

    public_key: dict[str, Any]
    challenge: bytes


@dataclass(frozen=True)
class NewPasskey:
    """A verified passkey, ready to store."""

    credential_id: bytes
    public_key: bytes
    sign_count: int
    transports: list[str]


@dataclass(frozen=True)
class LoginAnswer:
    """An authenticator's answer to a login, parsed but not yet verified."""

    #: Which passkey answered, to look up in the passkey table.
    credential_id: bytes
    #: The account handle the passkey was made for, when the authenticator gives it; it must
    #: match the handle of the account the credential is stored under.
    user_handle: bytes | None
    credential: AuthenticationCredential


def new_user_handle() -> bytes:
    """A random account handle for passkeys to carry, in place of anything that identifies the
    person: an authenticator may show it, and it outlives a change of login name."""
    return secrets.token_bytes(32)


def registration_options(
    party: Party,
    *,
    rp_name: str,
    user_handle: bytes,
    user_name: str,
    display_name: str,
    exclude: Iterable[bytes] = (),
) -> Options:
    """Start adding a passkey: the options a browser hands its authenticator.

    The passkey is discoverable, so it can log in without a login name typed first, and the
    authenticator is told which credentials (``exclude``) the account already holds, so it does
    not make a second passkey where it has one. ``rp_name`` is what the site is called on the
    person's device.
    """
    options = generate_registration_options(
        rp_id=party.rp_id,
        rp_name=rp_name,
        user_id=user_handle,
        user_name=user_name,
        user_display_name=display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=c) for c in exclude],
    )
    return Options(json.loads(options_to_json(options)), options.challenge)


def verify_registration(party: Party, credential: dict[str, Any], challenge: bytes) -> NewPasskey:
    """Finish adding a passkey: check the authenticator's answer to ``challenge``.

    ``credential`` is the browser's JSON for the new credential. Raises :class:`PasskeyRejected`
    if it is malformed, answers another challenge, or comes from another origin.
    """
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=party.rp_id,
            expected_origin=party.origin,
        )
    except _REJECTED as error:
        raise PasskeyRejected(str(error)) from error
    response = credential.get("response")
    transports = response.get("transports") if isinstance(response, dict) else None
    return NewPasskey(
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=[t for t in transports or [] if isinstance(t, str)],
    )


def authentication_options(party: Party) -> Options:
    """Start logging in with a passkey. Names nobody: the authenticator offers whichever of its
    passkeys belong to this site."""
    options = generate_authentication_options(
        rp_id=party.rp_id, user_verification=UserVerificationRequirement.PREFERRED
    )
    return Options(json.loads(options_to_json(options)), options.challenge)


def parse_login(credential: dict[str, Any]) -> LoginAnswer:
    """Read which passkey answered a login, before looking it up to verify the answer.

    Raises :class:`PasskeyRejected` if the answer is malformed.
    """
    try:
        parsed = parse_authentication_credential_json(credential)
    except _REJECTED as error:
        raise PasskeyRejected(str(error)) from error
    return LoginAnswer(parsed.raw_id, parsed.response.user_handle or None, parsed)


def verify_login(
    party: Party, answer: LoginAnswer, challenge: bytes, *, public_key: bytes, sign_count: int
) -> int:
    """Check a login answer against the stored passkey, and return its new signature counter.

    Raises :class:`PasskeyRejected` if the signature does not verify, answers another challenge,
    comes from another origin, or carries a counter that has not moved past ``sign_count``, the
    mark of a cloned key. An authenticator that keeps no counter sends zero every time, which
    passes.
    """
    try:
        verified = verify_authentication_response(
            credential=answer.credential,
            expected_challenge=challenge,
            expected_rp_id=party.rp_id,
            expected_origin=party.origin,
            credential_public_key=public_key,
            credential_current_sign_count=sign_count,
        )
    except _REJECTED as error:
        raise PasskeyRejected(str(error)) from error
    return verified.new_sign_count
