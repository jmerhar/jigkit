"""Passkey ceremonies, verified against a software authenticator."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request, Response
from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column
from webauthn.helpers import bytes_to_base64url

from jigkit.auth.passkeys import (
    MAX_CEREMONIES,
    Ceremonies,
    Party,
    PasskeyMixin,
    PasskeyRejected,
    authentication_options,
    clear_ceremony,
    hold_ceremony,
    new_user_handle,
    parse_login,
    registration_options,
    relying_party,
    request_party,
    verify_login,
    verify_registration,
)
from jigkit.db import create_engine, create_sessionmaker, session_scope
from jigkit.models import Base
from jigkit.testing.passkeys import SoftAuthenticator

PARTY = Party(rp_id="myapp.test", origin="http://myapp.test")


@pytest.fixture
def authenticator() -> SoftAuthenticator:
    return SoftAuthenticator(origin=PARTY.origin)


def register(authenticator: SoftAuthenticator, handle: bytes = b"h" * 32, **answer):
    """Run a registration ceremony through to its verified passkey."""
    options = registration_options(
        PARTY, rp_name="My app", user_handle=handle, user_name="ana", display_name="Ana"
    )
    return verify_registration(
        PARTY, authenticator.register(options.public_key, **answer), options.challenge
    )


class TestRegistration:
    def test_the_options_ask_for_a_discoverable_passkey_and_exclude_owned_ones(self) -> None:
        options = registration_options(
            PARTY,
            rp_name="My app",
            user_handle=b"\x01" * 32,
            user_name="ana",
            display_name="Ana Silva",
            exclude=[b"\x02" * 16],
        )

        public_key = options.public_key
        assert public_key["rp"] == {"id": "myapp.test", "name": "My app"}
        assert public_key["user"] == {
            "id": bytes_to_base64url(b"\x01" * 32),
            "name": "ana",
            "displayName": "Ana Silva",
        }
        assert public_key["authenticatorSelection"]["residentKey"] == "required"
        assert public_key["excludeCredentials"][0]["id"] == bytes_to_base64url(b"\x02" * 16)
        assert public_key["challenge"] == bytes_to_base64url(options.challenge)

    def test_a_genuine_answer_gives_a_passkey_to_store(
        self, authenticator: SoftAuthenticator
    ) -> None:
        passkey = register(authenticator)

        assert passkey.credential_id == authenticator.credentials[0].id
        assert passkey.public_key and passkey.sign_count == 0
        assert passkey.transports == ["internal", "hybrid"]

    def test_transports_that_are_not_strings_are_dropped(
        self, authenticator: SoftAuthenticator
    ) -> None:
        options = registration_options(
            PARTY, rp_name="x", user_handle=b"h", user_name="a", display_name="A"
        )
        answer = authenticator.register(options.public_key)
        answer["response"]["transports"] = ["usb", 7]

        assert verify_registration(PARTY, answer, options.challenge).transports == ["usb"]

    def test_an_answer_from_another_origin_is_rejected(
        self, authenticator: SoftAuthenticator
    ) -> None:
        with pytest.raises(PasskeyRejected):
            register(authenticator, origin="https://evil.test")

    def test_an_answer_to_another_challenge_is_rejected(
        self, authenticator: SoftAuthenticator
    ) -> None:
        options = registration_options(
            PARTY, rp_name="x", user_handle=b"h", user_name="a", display_name="A"
        )
        answer = authenticator.register(options.public_key)

        with pytest.raises(PasskeyRejected):
            verify_registration(PARTY, answer, b"another challenge")

    @pytest.mark.parametrize("answer", [{}, {"id": "x", "response": "nonsense"}])
    def test_a_malformed_answer_is_rejected(self, answer: dict) -> None:
        with pytest.raises(PasskeyRejected):
            verify_registration(PARTY, answer, b"challenge")

    def test_the_same_passkey_offered_again_has_the_same_credential(
        self, authenticator: SoftAuthenticator
    ) -> None:
        first = register(authenticator)
        again = register(authenticator, credential=authenticator.credentials[0])

        assert again.credential_id == first.credential_id
        assert len(authenticator.credentials) == 1

    def test_user_handles_are_random(self) -> None:
        assert len(new_user_handle()) == 32
        assert new_user_handle() != new_user_handle()


def log_in(authenticator: SoftAuthenticator, stored, *, sign_count: int | None = None, **answer):
    """Run a login ceremony against a stored passkey, returning the new counter."""
    options = authentication_options(PARTY)
    parsed = parse_login(authenticator.authenticate(options.public_key, **answer))
    assert parsed.credential_id == stored.credential_id
    return verify_login(
        PARTY,
        parsed,
        options.challenge,
        public_key=stored.public_key,
        sign_count=stored.sign_count if sign_count is None else sign_count,
    )


class TestLogin:
    def test_the_options_name_nobody(self) -> None:
        options = authentication_options(PARTY)

        assert options.public_key["rpId"] == "myapp.test"
        assert options.public_key.get("allowCredentials", []) == []

    def test_a_genuine_answer_logs_in_and_moves_the_counter(
        self, authenticator: SoftAuthenticator
    ) -> None:
        stored = register(authenticator, handle=b"ana's handle")
        options = authentication_options(PARTY)
        parsed = parse_login(authenticator.authenticate(options.public_key))

        assert parsed.user_handle == b"ana's handle"
        assert log_in(authenticator, stored) == 2

    def test_the_named_passkey_answers(self, authenticator: SoftAuthenticator) -> None:
        register(authenticator)
        second = register(authenticator)
        options = authentication_options(PARTY)
        answer = authenticator.authenticate(
            options.public_key, credential=authenticator.credentials[1]
        )

        assert parse_login(answer).credential_id == second.credential_id

    def test_an_answer_without_a_handle_has_none(self, authenticator: SoftAuthenticator) -> None:
        register(authenticator)
        answer = authenticator.authenticate(authentication_options(PARTY).public_key)
        answer["response"]["userHandle"] = ""

        assert parse_login(answer).user_handle is None

    def test_a_signature_from_another_origin_is_rejected(
        self, authenticator: SoftAuthenticator
    ) -> None:
        stored = register(authenticator)

        with pytest.raises(PasskeyRejected):
            log_in(authenticator, stored, origin="https://evil.test")

    def test_a_cloned_key_betrayed_by_its_counter_is_rejected(
        self, authenticator: SoftAuthenticator
    ) -> None:
        stored = register(authenticator)

        with pytest.raises(PasskeyRejected):
            log_in(authenticator, stored, sign_count=5)

    def test_another_keys_signature_is_rejected(self, authenticator: SoftAuthenticator) -> None:
        stored = register(authenticator)
        other = register(SoftAuthenticator(origin=PARTY.origin))
        options = authentication_options(PARTY)
        parsed = parse_login(authenticator.authenticate(options.public_key))

        with pytest.raises(PasskeyRejected):
            verify_login(
                PARTY, parsed, options.challenge, public_key=other.public_key, sign_count=0
            )
        assert stored.public_key != other.public_key

    @pytest.mark.parametrize("answer", [{"id": "x"}, {}, {"id": "!!", "rawId": "!!"}])
    def test_a_malformed_answer_is_rejected(self, answer: dict) -> None:
        with pytest.raises(PasskeyRejected):
            parse_login(answer)

    def test_a_malformed_user_handle_is_rejected(self, authenticator: SoftAuthenticator) -> None:
        register(authenticator)
        answer = authenticator.authenticate(authentication_options(PARTY).public_key)
        answer["response"]["userHandle"] = "!!!x"

        with pytest.raises(PasskeyRejected):
            parse_login(answer)


class TestParty:
    def test_the_public_url_decides_where_passkeys_belong(self) -> None:
        assert relying_party("https://costs.example.com/", "http", "127.0.0.1:18091") == Party(
            "costs.example.com", "https://costs.example.com"
        )
        assert (
            relying_party("https://costs.example.com:8443/app", "http", "x").origin
            == "https://costs.example.com:8443"
        )

    @pytest.mark.parametrize(
        ("host", "rp_id"),
        [("localhost:5173", "localhost"), ("myapp.test", "myapp.test"), ("[::1]:8000", "::1")],
    )
    def test_without_one_the_request_decides(self, host: str, rp_id: str) -> None:
        party = relying_party(None, "http", host)

        assert (party.rp_id, party.origin) == (rp_id, f"http://{host}")

    def test_from_a_request(self) -> None:
        scope = {
            "type": "http",
            "scheme": "https",
            "server": ("myapp.test", 443),
            "headers": [(b"host", b"myapp.test")],
            "path": "/",
            "query_string": b"",
        }

        assert request_party(Request(scope), None) == Party("myapp.test", "https://myapp.test")


class Clock:
    """A clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class TestCeremonies:
    def test_a_ceremony_is_finished_once_by_its_key(self) -> None:
        ceremonies = Ceremonies(clock=Clock())
        key = ceremonies.start(b"challenge", 7)

        ceremony = ceremonies.finish(key)

        assert ceremony is not None and (ceremony.challenge, ceremony.owner_id) == (b"challenge", 7)
        assert ceremonies.finish(key) is None
        assert ceremonies.finish(None) is None
        assert ceremonies.finish("unknown") is None

    def test_a_ceremony_expires(self) -> None:
        clock = Clock()
        ceremonies = Ceremonies(lifetime_seconds=60, clock=clock)
        old = ceremonies.start(b"old", None)
        clock.now = 30
        young = ceremonies.start(b"young", None)
        clock.now = 60

        assert ceremonies.finish(old) is None
        assert ceremonies.finish(young) is not None

    def test_expired_ceremonies_are_forgotten_when_another_starts(self) -> None:
        clock = Clock()
        ceremonies = Ceremonies(clock=clock)
        for _ in range(3):
            ceremonies.start(b"c", None)
        clock.now = 301

        ceremonies.start(b"c", None)

        assert len(ceremonies) == 1

    def test_the_oldest_are_forgotten_beyond_the_bound(self) -> None:
        ceremonies = Ceremonies(max_waiting=2, clock=Clock())
        first, second, third = (ceremonies.start(b"c", None) for _ in range(3))

        assert len(ceremonies) == 2
        assert ceremonies.finish(first) is None
        assert ceremonies.finish(second) and ceremonies.finish(third)
        assert MAX_CEREMONIES == 10_000


def cookie_app() -> FastAPI:
    """An application that holds and clears a ceremony's key."""
    app = FastAPI()

    @app.post("/start")
    async def start(request: Request, response: Response) -> dict[str, str]:
        hold_ceremony(response, request, "k3y", name="ceremony", path="/api/auth")
        return {}

    @app.post("/finish")
    async def finish(response: Response) -> dict[str, str]:
        clear_ceremony(response, name="ceremony", path="/api/auth")
        return {}

    return app


class TestCeremonyCookie:
    @pytest.mark.parametrize(
        ("base", "secure"), [("http://a.test", False), ("https://a.test", True)]
    )
    async def test_the_key_is_strict_short_lived_and_narrow(self, base: str, secure: bool) -> None:
        transport = httpx.ASGITransport(app=cookie_app())
        async with httpx.AsyncClient(transport=transport, base_url=base) as client:
            cookie = (await client.post("/start")).headers["set-cookie"]

        assert cookie.startswith("ceremony=k3y;")
        for part in ("HttpOnly", "Max-Age=300", "Path=/api/auth", "SameSite=strict"):
            assert part in cookie
        assert ("Secure" in cookie) is secure

    async def test_finishing_clears_it(self) -> None:
        transport = httpx.ASGITransport(app=cookie_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://a.test") as client:
            cookie = (await client.post("/finish")).headers["set-cookie"]

        assert cookie.startswith('ceremony="";') and "Max-Age=0" in cookie
        assert "Path=/api/auth" in cookie


class Owner(Base):
    """Whom the passkeys in these tests belong to."""

    __tablename__ = "test_passkey_owners"

    id: Mapped[int] = mapped_column(primary_key=True)


class OwnerPasskey(PasskeyMixin, Base):
    """The passkey table these tests use."""

    __tablename__ = "test_passkeys"

    owner_id: Mapped[int] = mapped_column(ForeignKey("test_passkey_owners.id", ondelete="CASCADE"))


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'passkeys.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all, tables=[Owner.__table__, OwnerPasskey.__table__]
        )
        await connection.execute(Owner.__table__.insert(), [{"id": 1}])
    yield engine
    await engine.dispose()


async def test_a_verified_passkey_is_stored_and_found_by_its_credential(
    engine: AsyncEngine, authenticator: SoftAuthenticator
) -> None:
    passkey = register(authenticator)
    factory = create_sessionmaker(engine)
    async with session_scope(factory) as db:
        db.add(
            OwnerPasskey(
                owner_id=1,
                credential_id=passkey.credential_id,
                public_key=passkey.public_key,
                sign_count=passkey.sign_count,
                transports=passkey.transports,
                label="Phone",
            )
        )
    async with session_scope(factory) as db:
        stored = (
            await db.execute(
                select(OwnerPasskey).where(OwnerPasskey.credential_id == passkey.credential_id)
            )
        ).scalar_one()

    assert stored.transports == ["internal", "hybrid"] and stored.label == "Phone"
    assert stored.created_at is not None and stored.last_used_at is None
    assert log_in(authenticator, stored) == 1
