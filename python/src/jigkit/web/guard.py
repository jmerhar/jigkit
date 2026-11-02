"""Requests the application refuses, and the headers it adds to every response."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

#: Methods that change something, which only the application's own pages may send.
WRITES = frozenset({"POST", "PUT", "PATCH", "DELETE"})
#: The header every write must carry. A page on another site cannot add a custom header to a
#: request without a CORS preflight, which an application built on this never grants.
WRITE_HEADER = "X-Requested-With"


def origin_allowed(origin: str | None, host: str | None, public_url: str | None) -> bool:
    """Whether a write's Origin header is this application's own.

    No Origin at all is allowed: browsers send one on every cross-origin write, so its absence
    means a same-origin request or a client that is not a browser, and the write header still
    has to be there. Otherwise the origin must be the configured public URL's, or name the host
    the request was sent to; an opaque ``null`` origin never does.
    """
    if origin is None:
        return True
    allowed = set()
    if public_url:
        parts = urlsplit(public_url)
        allowed.add(f"{parts.scheme}://{parts.netloc}".lower())
    if host:
        allowed.update({f"http://{host}".lower(), f"https://{host}".lower()})
    return origin.lower() in allowed


def install_write_guard(
    app: FastAPI, *, value: str, public_url: str | None, prefix: str = "/api"
) -> None:
    """Refuse a write under ``prefix`` unless it plainly comes from the application's own pages.

    Every write must carry ``X-Requested-With: <value>``, and any Origin it has must be the
    application's own; otherwise it is answered 403 with ``missing_write_header`` or
    ``foreign_origin``. With a SameSite=Lax session cookie this is the second of two locks
    against cross-site writes.
    """

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in WRITES and request.url.path.startswith(f"{prefix}/"):
            if request.headers.get(WRITE_HEADER) != value:
                return JSONResponse({"detail": "missing_write_header"}, status_code=403)
            if not origin_allowed(
                request.headers.get("origin"), request.headers.get("host"), public_url
            ):
                return JSONResponse({"detail": "foreign_origin"}, status_code=403)
        return await call_next(request)


#: Headers added to every response that does not set them itself.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
}


def install_security_headers(app: FastAPI) -> None:
    """Add :data:`SECURITY_HEADERS` to every response that has not set them itself.

    Responses are never sniffed into another type, never framed by another site, and send their
    URL as a referrer only to the application itself. A response that sets one of these headers
    keeps its own, so a route that needs a fuller Content-Security-Policy can send one.
    """

    @app.middleware("http")
    async def secure(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
