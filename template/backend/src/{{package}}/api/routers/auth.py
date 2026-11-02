"""Logging in and out, and the browsers logged in."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from jigkit.auth import burn_password_check, verify_password
from sqlalchemy import select

from ...auth import SESSION_COOKIE, SESSIONS
from ...models import Session, User
from .. import cookies
from ..deps import DbDep, ServicesDep, SessionDep, client_address
from ..schemas import LoginIn, Me, SessionOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def log_in(
    body: LoginIn, request: Request, response: Response, db: DbDep, services: ServicesDep
) -> Me:
    """Log in with a login and password, and start a session.

    A login naming nobody costs as long as a wrong password, so the answer does not tell which
    logins exist; failures count against the address, which is refused for a minute after too
    many.
    """
    address = client_address(request)
    if services.throttle.blocked(address):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
    user = (
        await db.execute(select(User).where(User.login == body.login.strip().lower()))
    ).scalar_one_or_none()
    if user is None:
        burn_password_check(body.password)
    if user is None or not verify_password(user.password_hash, body.password):
        services.throttle.failed(address)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_login")
    services.throttle.succeeded(address)
    token = await SESSIONS.open(db, user.id, request.headers.get("user-agent", ""))
    cookies.issue(response, request, services.settings, token)
    return cookies.describe(user, services.settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def log_out(request: Request, response: Response, db: DbDep, services: ServicesDep) -> None:
    """End this browser's session, if it has one."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await SESSIONS.end(db, token)
    cookies.clear(response, request, services.settings)


@router.get("/me")
async def me(session: SessionDep, services: ServicesDep) -> Me:
    """The user logged in."""
    return cookies.describe(session.user, services.settings)


@router.get("/sessions")
async def sessions(session: SessionDep, db: DbDep) -> list[SessionOut]:
    """The browsers this user is logged in on, this one marked."""
    rows = await db.execute(
        select(Session)
        .where(Session.user_id == session.user_id)
        .order_by(Session.last_seen_at.desc())
    )
    return [
        SessionOut.model_validate(row).model_copy(update={"current": row.id == session.id})
        for row in rows.scalars()
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(session_id: int, session: SessionDep, db: DbDep) -> None:
    """Log out another browser of this user's."""
    other = await db.get(Session, session_id)
    if other is None or other.user_id != session.user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    await db.delete(other)
