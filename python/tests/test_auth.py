"""Passwords, the login throttle, the session cookie and database sessions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request, Response
from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column

from jigkit.auth import (
    LoginThrottle,
    PasswordTooShort,
    burn_password_check,
    clear_session_cookie,
    cookie_secure,
    hash_password,
    issue_session_cookie,
    verify_password,
)
from jigkit.auth.sessions import SessionMixin, SessionStore, token_digest
from jigkit.db import create_engine, create_sessionmaker, session_scope
from jigkit.models import Base


class TestPasswords:
    def test_a_password_verifies_against_its_own_hash_only(self) -> None:
        stored = hash_password("correct horse battery")

        assert stored.startswith("$argon2id$")
        assert verify_password(stored, "correct horse battery")
        assert not verify_password(stored, "correct horse battery!")

    def test_a_short_password_is_refused(self) -> None:
        with pytest.raises(PasswordTooShort, match="at least 10"):
            hash_password("short")
        assert hash_password("abcd", min_length=4)

    def test_a_malformed_hash_simply_does_not_match(self) -> None:
        assert not verify_password("not-a-hash", "anything at all")

    def test_burning_a_check_for_nobody_returns_nothing(self) -> None:
        assert burn_password_check("whatever was typed") is None


class Clock:
    """A clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class TestLoginThrottle:
    def test_failures_past_the_limit_block_the_address(self) -> None:
        throttle = LoginThrottle(3, clock=Clock())
        for _ in range(3):
            assert not throttle.blocked("a")
            throttle.failed("a")

        assert throttle.blocked("a")
        assert not throttle.blocked("b")

    def test_failures_older_than_a_minute_no_longer_count(self) -> None:
        clock = Clock()
        throttle = LoginThrottle(2, clock=clock)
        throttle.failed("a")
        throttle.failed("a")
        assert throttle.blocked("a")

        clock.now = 60.0

        assert not throttle.blocked("a")

    def test_a_success_forgets_the_failures(self) -> None:
        throttle = LoginThrottle(2, clock=Clock())
        throttle.failed("a")
        throttle.failed("a")

        throttle.succeeded("a")

        assert not throttle.blocked("a")

    def test_asking_never_adds_an_address(self) -> None:
        throttle = LoginThrottle(2, clock=Clock())

        for i in range(100):
            throttle.blocked(f"10.0.0.{i}")

        assert len(throttle._failures) == 0

    def test_the_oldest_addresses_are_forgotten_beyond_the_bound(self) -> None:
        throttle = LoginThrottle(1, max_clients=2, clock=Clock())
        throttle.failed("a")
        throttle.failed("b")
        throttle.failed("a")
        throttle.failed("c")

        assert list(throttle._failures) == ["a", "c"]
        assert throttle.blocked("a")
        assert not throttle.blocked("b")


def cookie_app() -> FastAPI:
    """An application that logs in and out with the session cookie."""
    app = FastAPI()

    @app.post("/login")
    async def login(request: Request, response: Response, secure: str = "") -> dict[str, str]:
        override = {"yes": True, "no": False}.get(secure)
        issue_session_cookie(
            response, request, name="sid", token="t0k", max_age_seconds=3600, secure=override
        )
        return {}

    @app.post("/logout")
    async def logout(request: Request, response: Response) -> dict[str, str]:
        clear_session_cookie(response, request, name="sid")
        return {}

    return app


async def post(base_url: str, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=cookie_app())
    async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
        return await client.post(path)


class TestSessionCookie:
    async def test_the_cookie_is_http_only_lax_and_lasts_its_lifetime(self) -> None:
        cookie = (await post("http://app.test", "/login")).headers["set-cookie"]

        assert cookie.startswith("sid=t0k;")
        for part in ("HttpOnly", "Max-Age=3600", "Path=/", "SameSite=lax"):
            assert part in cookie
        assert "Secure" not in cookie

    async def test_https_requests_get_a_secure_cookie(self) -> None:
        assert "Secure" in (await post("https://app.test", "/login")).headers["set-cookie"]

    @pytest.mark.parametrize(("flag", "secure"), [("yes", True), ("no", False)])
    async def test_the_configured_flag_wins(self, flag: str, secure: bool) -> None:
        base = "http://app.test" if secure else "https://app.test"
        cookie = (await post(base, f"/login?secure={flag}")).headers["set-cookie"]

        assert ("Secure" in cookie) is secure

    async def test_a_forged_forwarded_proto_does_not_count(self) -> None:
        # Only uvicorn, believing a trusted proxy, may turn the header into the request's scheme.
        transport = httpx.ASGITransport(app=cookie_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://app.test") as client:
            response = await client.post("/login", headers={"X-Forwarded-Proto": "https"})

        assert "Secure" not in response.headers["set-cookie"]

    async def test_logging_out_clears_the_cookie(self) -> None:
        cookie = (await post("http://app.test", "/logout")).headers["set-cookie"]

        assert cookie.startswith('sid="";') and "Max-Age=0" in cookie

    def test_cookie_secure(self) -> None:
        scope = {
            "type": "http",
            "scheme": "https",
            "server": ("app.test", 443),
            "headers": [],
            "path": "/",
            "query_string": b"",
        }

        assert cookie_secure(Request(scope), None) is True
        assert cookie_secure(Request(scope), False) is False


class Account(Base):
    """Whom the sessions in these tests log in."""

    __tablename__ = "test_auth_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))


class AccountSession(SessionMixin, Base):
    """The sessions table these tests use."""

    __tablename__ = "test_auth_sessions"

    account_id: Mapped[int] = mapped_column(ForeignKey("test_auth_accounts.id", ondelete="CASCADE"))


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all, tables=[Account.__table__, AccountSession.__table__]
        )
        await connection.execute(
            Account.__table__.insert(), [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        )
    yield engine
    await engine.dispose()


STORE = SessionStore(AccountSession, owner="account_id")


class TestSessions:
    async def test_a_session_opens_and_is_found_by_its_token(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as db:
            token = await STORE.open(db, 1, "Firefox " + "x" * 400)
        async with session_scope(factory) as db:
            found = await STORE.find(db, token)

        assert found is not None and found.account_id == 1
        assert found.token_hash == token_digest(token) != token
        assert len(found.user_agent) == 300
        assert found.expires_at - found.created_at == timedelta(days=90)

    async def test_an_unknown_or_expired_token_finds_nothing(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as db:
            token = await STORE.open(db, 1)
        later = datetime.now(UTC) + timedelta(days=91)
        async with session_scope(factory) as db:
            assert await STORE.find(db, "not-a-token") is None
            assert await STORE.find(db, token, now=later) is None

    async def test_a_stale_session_is_extended_and_a_fresh_one_left_alone(
        self, engine: AsyncEngine
    ) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as db:
            token = await STORE.open(db, 1)
        async with session_scope(factory) as db:
            session = await STORE.find(db, token)
            opened = session.expires_at
        soon = datetime.now(UTC) + timedelta(hours=1)
        async with session_scope(factory) as db:
            assert (await STORE.find(db, token, now=soon)).expires_at == opened
        later = datetime.now(UTC) + timedelta(days=2)
        async with session_scope(factory) as db:
            await STORE.find(db, token, now=later)
        async with session_scope(factory) as db:
            session = await STORE.find(db, token, now=later)

        assert session.last_seen_at == later
        assert session.expires_at == later + timedelta(days=90)

    async def test_ending_a_session_ends_only_that_one(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as db:
            first, second = await STORE.open(db, 1), await STORE.open(db, 1)
        async with session_scope(factory) as db:
            await STORE.end(db, first)
        async with session_scope(factory) as db:
            assert await STORE.find(db, first) is None
            assert await STORE.find(db, second) is not None

    async def test_ending_all_of_an_owners_sessions_can_keep_one(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as db:
            mine = [await STORE.open(db, 1) for _ in range(3)]
            theirs = await STORE.open(db, 2)
        async with session_scope(factory) as db:
            kept = await STORE.find(db, mine[0])
            await STORE.end_all(db, 1, keep=kept.id)
        async with session_scope(factory) as db:
            assert await STORE.find(db, mine[0]) is not None
            assert await STORE.find(db, mine[1]) is None
            assert await STORE.find(db, theirs) is not None
            await STORE.end_all(db, 1)
        async with session_scope(factory) as db:
            assert await STORE.find(db, mine[0]) is None

    async def test_pruning_deletes_only_expired_sessions(self, engine: AsyncEngine) -> None:
        factory = create_sessionmaker(engine)
        async with session_scope(factory) as db:
            await STORE.open(db, 1)
            await STORE.open(db, 2)
        async with session_scope(factory) as db:
            assert await STORE.prune(db) == 0
            assert await STORE.prune(db, now=datetime.now(UTC) + timedelta(days=91)) == 2
        async with session_scope(factory) as db:
            count = (await db.execute(select(func.count()).select_from(AccountSession))).scalar()

        assert count == 0
