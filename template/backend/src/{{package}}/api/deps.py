"""Request dependencies and the services the application holds for its lifetime."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from jigkit.auth import LoginThrottle
from jigkit.auth.passkeys import Ceremonies
from jigkit.db import create_engine, create_sessionmaker, session_scope
from jigkit.notify import AppriseSender, Sender
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ..auth import SESSION_COOKIE, SESSIONS
from ..config import Settings
from ..models import Session, User


@dataclass
class Services:
    """What the application builds once at startup and closes at shutdown."""

    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    throttle: LoginThrottle
    sender: Sender
    #: Passkey challenges waiting for the authenticator's answer.
    ceremonies: Ceremonies = field(default_factory=Ceremonies)
    #: Held while the first account is made, so two browsers racing through setup cannot both
    #: make one.
    setup_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def build_services(settings: Settings, sender: Sender | None = None) -> Services:
    """Build the services for ``settings``. Opens no connection until one is used."""
    engine = create_engine(settings.resolved_database_url)
    return Services(
        settings=settings,
        engine=engine,
        sessionmaker=create_sessionmaker(engine),
        throttle=LoginThrottle(settings.login_attempts_per_minute),
        sender=sender or AppriseSender(),
    )


def get_services(request: Request) -> Services:
    """The services the running application was started with."""
    return request.app.state.services


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """A session for one request, committed when the handler succeeds and rolled back if not."""
    async with session_scope(get_services(request).sessionmaker) as session:
        yield session


ServicesDep = Annotated[Services, Depends(get_services)]
# Function scope commits before the response is sent, so a client that acts on a response (the
# session cookie from a login, the id of a new note) finds what it describes already stored.
DbDep = Annotated[AsyncSession, Depends(get_db, scope="function")]


async def get_session(request: Request, db: DbDep) -> Session:
    """The browser's live session; without one the request is refused with 401."""
    token = request.cookies.get(SESSION_COOKIE)
    session = await SESSIONS.find(db, token) if token else None
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return session


SessionDep = Annotated[Session, Depends(get_session)]


async def get_user(session: SessionDep) -> User:
    """The user logged in."""
    return session.user


UserDep = Annotated[User, Depends(get_user)]


def client_address(request: Request) -> str:
    """The address the login throttle counts: the client uvicorn believes behind its proxies."""
    return request.client.host if request.client else "unknown"
