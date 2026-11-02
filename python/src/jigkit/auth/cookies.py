"""The cookie a logged-in browser carries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request, Response


def cookie_secure(request: Request, override: bool | None) -> bool:
    """Whether the session cookie gets the Secure flag: as configured, else for HTTPS requests.

    The scheme is the request's own, which uvicorn takes from X-Forwarded-Proto only when the
    proxy is one it believes (``FORWARDED_ALLOW_IPS``); the header itself is never read here,
    since any client can send it. Following the scheme lets an instance on a private network be
    used over plain HTTP, where a Secure cookie would be dropped and login would look broken.
    """
    if override is not None:
        return override
    return request.url.scheme == "https"


def issue_session_cookie(
    response: Response,
    request: Request,
    *,
    name: str,
    token: str,
    max_age_seconds: int,
    secure: bool | None = None,
) -> None:
    """Put a session token in the browser.

    HttpOnly, so no script can read it; SameSite=Lax, so a page elsewhere cannot send it with a
    write, while a link to the application from an email still arrives logged in.
    """
    response.set_cookie(
        name,
        token,
        max_age=max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(request, secure),
        path="/",
    )


def clear_session_cookie(
    response: Response, request: Request, *, name: str, secure: bool | None = None
) -> None:
    """Remove the session token from the browser."""
    response.delete_cookie(
        name, httponly=True, samesite="lax", secure=cookie_secure(request, secure), path="/"
    )
