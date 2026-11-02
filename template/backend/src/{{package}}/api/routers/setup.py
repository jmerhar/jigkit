"""First-run setup: the first account, made by whoever opens a new installation first."""

from fastapi import APIRouter, HTTPException, Request, Response, status
from jigkit.auth import PasswordTooShort, hash_password
from sqlalchemy import func, select

from ...auth import SESSIONS
from ...models import User
from .. import cookies
from ..deps import DbDep, ServicesDep
from ..schemas import LANGUAGES, Me, SetupIn, SetupState

router = APIRouter(prefix="/setup", tags=["setup"])


async def _anyone(db: DbDep) -> bool:
    return bool((await db.execute(select(func.count()).select_from(User))).scalar())


@router.get("")
async def setup_state(db: DbDep) -> SetupState:
    """Whether the first account still has to be made."""
    return SetupState(required=not await _anyone(db))


@router.post("", status_code=status.HTTP_201_CREATED)
async def set_up(
    body: SetupIn, request: Request, response: Response, db: DbDep, services: ServicesDep
) -> Me:
    """Make the first account and log it in. Refused once anyone exists.

    The lock keeps two browsers racing through setup from both making one: the second finds the
    first's account once it gets the lock.
    """
    async with services.setup_lock:
        if await _anyone(db):
            raise HTTPException(status.HTTP_409_CONFLICT, "already_set_up")
        try:
            password_hash = hash_password(body.password)
        except PasswordTooShort:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "password_too_short"
            ) from None
        user = User(
            name=body.name.strip(),
            login=body.login.strip().lower(),
            password_hash=password_hash,
            language=body.language if body.language in LANGUAGES else None,
        )
        db.add(user)
        await db.flush()
        token = await SESSIONS.open(db, user.id, request.headers.get("user-agent", ""))
        await db.commit()
    cookies.issue(response, request, services.settings, token)
    return cookies.describe(user, services.settings)
