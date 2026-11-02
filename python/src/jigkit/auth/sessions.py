"""Logins kept in the database (extras ``auth`` and ``db``): revocable, and only hashed.

An application declares its session table with :class:`SessionMixin` and its own owner column::

    class Session(SessionMixin, Base):
        __tablename__ = "session"
        person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))

    SESSIONS = SessionStore(Session, owner="person_id")

The browser keeps the token; the table keeps only its SHA-256, so a copy of the database cannot
be replayed as logins. Ending a session deletes its row, so logging out really ends it.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Integer, String, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from jigkit.models import UtcDateTime, utcnow

#: How long a login lasts without being used; each use extends it.
SESSION_LIFETIME = timedelta(days=90)
#: How stale a session's expiry may grow before a request writes a new one, so an active browser
#: does not cost a write on every request.
SESSION_REFRESH = timedelta(days=1)
#: The longest user agent kept, to tell a person's sessions apart.
USER_AGENT_LENGTH = 300


def token_digest(token: str) -> str:
    """The SHA-256 a session token is stored as."""
    return hashlib.sha256(token.encode()).hexdigest()


class SessionMixin:
    """The columns of a session table; the application adds the owner's foreign key."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    user_agent: Mapped[str] = mapped_column(String(USER_AGENT_LENGTH), default="")


class SessionStore:
    """Opens, finds and ends the sessions in one table.

    ``owner`` names the table's column holding who the session logs in.
    """

    def __init__(
        self,
        model: type[Any],
        *,
        owner: str,
        lifetime: timedelta = SESSION_LIFETIME,
        refresh: timedelta = SESSION_REFRESH,
    ) -> None:
        self.model = model
        self.owner = owner
        self.lifetime = lifetime
        self.refresh = refresh

    async def open(self, db: AsyncSession, owner_id: int, user_agent: str = "") -> str:
        """Start a session for ``owner_id`` and return its token, which only the browser keeps."""
        token = secrets.token_urlsafe(32)
        now = utcnow()
        db.add(
            self.model(
                token_hash=token_digest(token),
                created_at=now,
                last_seen_at=now,
                expires_at=now + self.lifetime,
                user_agent=user_agent[:USER_AGENT_LENGTH],
                **{self.owner: owner_id},
            )
        )
        await db.flush()
        return token

    async def find(self, db: AsyncSession, token: str, now: datetime | None = None) -> Any | None:
        """The live session ``token`` belongs to, its expiry extended once it is stale, or None."""
        now = now or utcnow()
        session = (
            await db.execute(select(self.model).where(self.model.token_hash == token_digest(token)))
        ).scalar_one_or_none()
        if session is None or session.expires_at <= now:
            return None
        if now - session.last_seen_at >= self.refresh:
            session.last_seen_at = now
            session.expires_at = now + self.lifetime
        return session

    async def end(self, db: AsyncSession, token: str) -> None:
        """End the session ``token`` belongs to, if there is one."""
        await db.execute(delete(self.model).where(self.model.token_hash == token_digest(token)))

    async def end_all(self, db: AsyncSession, owner_id: int, *, keep: int | None = None) -> None:
        """End every session of ``owner_id``, except the one with id ``keep`` when given."""
        statement = delete(self.model).where(getattr(self.model, self.owner) == owner_id)
        if keep is not None:
            statement = statement.where(self.model.id != keep)
        await db.execute(statement)

    async def prune(self, db: AsyncSession, now: datetime | None = None) -> int:
        """Delete every expired session, and return how many there were."""
        result = await db.execute(
            delete(self.model).where(self.model.expires_at <= (now or utcnow()))
        )
        return result.rowcount or 0
