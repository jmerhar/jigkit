"""Invitations (extras ``auth`` and ``db``): a one-time link that lets someone choose their own
password, for an account an administrator made, or to reset one.

An application declares its invitation table with :class:`InvitationMixin` and its own owner
column, as it does its sessions::

    class Invitation(InvitationMixin, Base):
        __tablename__ = "invitation"
        person_id: Mapped[int] = mapped_column(ForeignKey("person.id", ondelete="CASCADE"))

    INVITATIONS = InvitationStore(Invitation, owner="person_id")

The administrator sends the link (the application's own page, carrying the token) however they
like. The table keeps only the token's SHA-256, so a copy of the database holds no usable link;
an owner has at most one invitation, a new one replacing the last, and redeeming one deletes it,
so a link works once.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Integer, String, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from jigkit.auth.sessions import token_digest
from jigkit.models import UtcDateTime, utcnow

#: How long an invitation can be used.
INVITATION_LIFETIME = timedelta(days=7)


class InvitationMixin:
    """The columns of an invitation table; the application adds the owner's foreign key."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)


class InvitationStore:
    """Issues, finds, redeems and revokes the invitations in one table.

    ``owner`` names the table's column holding whose account the invitation opens.
    """

    def __init__(
        self, model: type[Any], *, owner: str, lifetime: timedelta = INVITATION_LIFETIME
    ) -> None:
        self.model = model
        self.owner = owner
        self.lifetime = lifetime

    async def issue(self, db: AsyncSession, owner_id: int, now: datetime | None = None) -> str:
        """A new invitation for ``owner_id``, replacing any earlier one; returns its token, which
        only the link carries."""
        await self.revoke(db, owner_id)
        token = secrets.token_urlsafe(32)
        now = now or utcnow()
        db.add(
            self.model(
                token_hash=token_digest(token),
                created_at=now,
                expires_at=now + self.lifetime,
                **{self.owner: owner_id},
            )
        )
        await db.flush()
        return token

    async def find(self, db: AsyncSession, token: str, now: datetime | None = None) -> Any | None:
        """The live invitation ``token`` belongs to, or None when there is none or it expired."""
        invitation = (
            await db.execute(select(self.model).where(self.model.token_hash == token_digest(token)))
        ).scalar_one_or_none()
        if invitation is None or invitation.expires_at <= (now or utcnow()):
            return None
        return invitation

    async def redeem(self, db: AsyncSession, token: str, now: datetime | None = None) -> int | None:
        """Use the invitation ``token`` belongs to: its owner's id, or None when it is not live.
        It is deleted, so the link works once."""
        invitation = await self.find(db, token, now)
        if invitation is None:
            return None
        owner_id = getattr(invitation, self.owner)
        await db.delete(invitation)
        await db.flush()
        return owner_id

    async def pending(
        self, db: AsyncSession, owner_id: int, now: datetime | None = None
    ) -> Any | None:
        """``owner_id``'s live invitation, or None."""
        invitation = (
            await db.execute(select(self.model).where(getattr(self.model, self.owner) == owner_id))
        ).scalar_one_or_none()
        if invitation is None or invitation.expires_at <= (now or utcnow()):
            return None
        return invitation

    async def revoke(self, db: AsyncSession, owner_id: int) -> None:
        """Delete ``owner_id``'s invitation, if there is one."""
        await db.execute(delete(self.model).where(getattr(self.model, self.owner) == owner_id))

    async def prune(self, db: AsyncSession, now: datetime | None = None) -> int:
        """Delete every expired invitation, and return how many there were."""
        result = await db.execute(
            delete(self.model).where(self.model.expires_at <= (now or utcnow()))
        )
        return result.rowcount or 0
