"""The session cookie, and the user a login answers with."""

from fastapi import Request, Response
from jigkit.auth import clear_session_cookie, issue_session_cookie

from ..auth import SESSION_COOKIE, SESSION_LIFETIME
from ..config import Settings
from ..models import User
from .schemas import Me


def issue(response: Response, request: Request, settings: Settings, token: str) -> None:
    """Put a session token in the browser: HttpOnly, SameSite=Lax, for the session's lifetime."""
    issue_session_cookie(
        response,
        request,
        name=SESSION_COOKIE,
        token=token,
        max_age_seconds=int(SESSION_LIFETIME.total_seconds()),
        secure=settings.cookie_secure,
    )


def clear(response: Response, request: Request, settings: Settings) -> None:
    """Remove the session token from the browser."""
    clear_session_cookie(response, request, name=SESSION_COOKIE, secure=settings.cookie_secure)


def describe(user: User, settings: Settings) -> Me:
    """The user logged in, as the interface sees them."""
    return Me(
        id=user.id,
        name=user.name,
        login=user.login,
        language=user.language,
        notifications=bool(settings.notify_url),
    )
