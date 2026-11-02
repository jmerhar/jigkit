"""The database's tables, on jigkit's declarative base.

jigkit's base names every constraint deterministically, so migrations generated on different
machines agree; ``UtcDateTime`` keeps times timezone-aware in SQLite; the session and passkey
tables take their columns from jigkit's mixins and add who they belong to.
"""

from __future__ import annotations

from jigkit.auth.passkeys import PasskeyMixin
from jigkit.auth.sessions import SessionMixin
from jigkit.models import Base, TimestampMixin, utcnow
from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

__all__ = ["Base", "Note", "Passkey", "Session", "User", "utcnow"]


class User(TimestampMixin, Base):
    """Someone who logs in."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    login: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    #: The language the interface uses for them, or None to follow their browser.
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    #: The handle their passkeys carry in place of anything that identifies them; made with the
    #: first passkey.
    webauthn_handle: Mapped[bytes | None] = mapped_column(
        LargeBinary(64), unique=True, nullable=True
    )


class Session(SessionMixin, Base):
    """A browser that is logged in."""

    __tablename__ = "session"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    user: Mapped[User] = relationship(lazy="joined")


class Passkey(PasskeyMixin, Base):
    """A passkey someone logs in with instead of their password."""

    __tablename__ = "passkey"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    user: Mapped[User] = relationship(lazy="joined")


class Note(TimestampMixin, Base):
    """A note someone keeps: the application's own data, where a new app starts adding its own."""

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
