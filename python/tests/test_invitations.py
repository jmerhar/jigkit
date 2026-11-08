"""Invitations: a one-time link for someone to choose their own password."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import ForeignKey, String, func, select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Mapped, mapped_column

from jigkit.auth.invitations import INVITATION_LIFETIME, InvitationMixin, InvitationStore
from jigkit.auth.sessions import token_digest
from jigkit.db import create_engine, create_sessionmaker, session_scope
from jigkit.models import Base

NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


class Member(Base):
    """Whom the invitations in these tests are for."""

    __tablename__ = "test_invitation_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(20))


class MemberInvitation(InvitationMixin, Base):
    """The invitations table these tests use."""

    __tablename__ = "test_invitations"

    member_id: Mapped[int] = mapped_column(
        ForeignKey("test_invitation_members.id", ondelete="CASCADE")
    )


STORE = InvitationStore(MemberInvitation, owner="member_id")


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncIterator:
    engine: AsyncEngine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'invitations.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all, tables=[Member.__table__, MemberInvitation.__table__]
        )
        await connection.execute(
            Member.__table__.insert(), [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        )
    yield create_sessionmaker(engine)
    await engine.dispose()


async def count(factory) -> int:
    async with session_scope(factory) as db:
        return (await db.execute(select(func.count()).select_from(MemberInvitation))).scalar_one()


async def test_an_invitation_is_found_by_its_token_and_keeps_only_its_hash(factory) -> None:
    async with session_scope(factory) as db:
        token = await STORE.issue(db, 1, NOW)
    async with session_scope(factory) as db:
        found = await STORE.find(db, token, NOW)
        pending = await STORE.pending(db, 1, NOW)

    assert found is not None and found.member_id == 1
    assert found.token_hash == token_digest(token) != token
    assert found.expires_at - found.created_at == INVITATION_LIFETIME == timedelta(days=7)
    assert pending is not None and pending.id == found.id


async def test_a_link_works_once(factory) -> None:
    async with session_scope(factory) as db:
        token = await STORE.issue(db, 1, NOW)
    async with session_scope(factory) as db:
        assert await STORE.redeem(db, token, NOW) == 1
    async with session_scope(factory) as db:
        assert await STORE.redeem(db, token, NOW) is None
        assert await STORE.pending(db, 1, NOW) is None


async def test_an_expired_or_unknown_link_opens_nothing(factory) -> None:
    async with session_scope(factory) as db:
        token = await STORE.issue(db, 1, NOW)
    later = NOW + INVITATION_LIFETIME

    async with session_scope(factory) as db:
        assert await STORE.find(db, token, later) is None
        assert await STORE.pending(db, 1, later) is None
        assert await STORE.redeem(db, token, later) is None
        assert await STORE.find(db, "guess", NOW) is None
    assert await count(factory) == 1


async def test_a_new_invitation_replaces_the_last_and_leaves_others_alone(factory) -> None:
    async with session_scope(factory) as db:
        first = await STORE.issue(db, 1, NOW)
        other = await STORE.issue(db, 2, NOW)
        second = await STORE.issue(db, 1, NOW)

    async with session_scope(factory) as db:
        assert await STORE.find(db, first, NOW) is None
        assert (await STORE.find(db, second, NOW)).member_id == 1
        assert (await STORE.find(db, other, NOW)).member_id == 2


async def test_revoking_and_pruning(factory) -> None:
    async with session_scope(factory) as db:
        await STORE.issue(db, 1, NOW)
        await STORE.issue(db, 2, NOW - INVITATION_LIFETIME)
    async with session_scope(factory) as db:
        assert await STORE.prune(db, NOW) == 1
        await STORE.revoke(db, 1)
    assert await count(factory) == 0


async def test_the_lifetime_can_be_chosen(factory) -> None:
    store = InvitationStore(MemberInvitation, owner="member_id", lifetime=timedelta(days=1))
    async with session_scope(factory) as db:
        token = await store.issue(db, 1)
        found = await store.find(db, token)

    assert found is not None and found.expires_at - found.created_at == timedelta(days=1)
