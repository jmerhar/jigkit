"""A fail-closed access policy: every route needs a credential unless it is declared open.

An application lists the routes reachable without one, as ``(method, full path template)``
pairs, and mounts the policy once as a global dependency::

    POLICY = AccessPolicy(
        {("GET", "/api/health"), ("POST", "/api/auth/login")},
        allow=lambda request: is_logged_in(request),
        prefix="/api",
    )
    app.include_router(api, prefix="/api", dependencies=[Depends(POLICY)])

A route added without touching the list needs the credential; the mistake that remains possible
is a page that breaks for logged-out visitors, not a write left open to everyone, as a
forgotten per-route dependency would leave it. :func:`route_templates` and
:meth:`AccessPolicy.unknown` let a test hold the list to the application's real route table.

The policy keys off the route the router matched rather than the requested URL, so a
declaration cannot cover a neighbouring path.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status

#: A route as ``(method, full path template)``, such as ``("GET", "/api/items/{item_id}")``.
Route = tuple[str, str]


def route_templates(app: FastAPI) -> set[Route]:
    """Every ``(method, full path template)`` the application serves, from its OpenAPI schema.

    The schema reports full templates however the routers were nested, which the route objects
    themselves do not across FastAPI versions. Routes left out of the schema
    (``include_in_schema=False``) are left out here too.
    """
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


class AccessPolicy:
    """A FastAPI dependency refusing every request to an undeclared route without a credential.

    ``open_routes`` are reachable by anyone; any other route needs ``allow(request)``, which
    may be async, to return true, or the request is refused with ``status_code`` and
    ``detail``. ``prefix`` is where the guarded routers are mounted: a matched route reports its
    path relative to its mount point in some FastAPI versions and in full in others, so both
    readings are checked.
    """

    def __init__(
        self,
        open_routes: Iterable[Route],
        *,
        allow: Callable[[Request], bool | Awaitable[bool]],
        prefix: str = "",
        status_code: int = status.HTTP_403_FORBIDDEN,
        detail: str = "forbidden",
    ) -> None:
        self.open_routes = frozenset((method.upper(), path) for method, path in open_routes)
        self._allow = allow
        self._prefix = prefix.rstrip("/")
        self._status_code = status_code
        self._detail = detail

    def is_open(self, method: str, route_path: str) -> bool:
        """Whether a matched route, by its own reported path, is reachable without a credential."""
        method = method.upper()
        return any(
            (method, template) in self.open_routes
            for template in (route_path, self._prefix + route_path)
        )

    def unknown(self, app: FastAPI) -> set[Route]:
        """Open routes the application does not serve: a typo, or a route since removed."""
        return set(self.open_routes - route_templates(app))

    async def __call__(self, request: Request) -> None:
        """Let the request through if its route is open or the credential checks out.

        A request that matched no route has no declaration, so it needs the credential; in
        practice an unmatched path is answered with a 404 before dependencies run.
        """
        route: Any = request.scope.get("route")
        route_path = getattr(route, "path", None)
        if route_path is not None and self.is_open(request.method, route_path):
            return
        allowed = self._allow(request)
        if inspect.isawaitable(allowed):
            allowed = await allowed
        if not allowed:
            raise HTTPException(self._status_code, self._detail)
