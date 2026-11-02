"""The endpoint a container's health probe calls."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Health(BaseModel):
    """The application's state as the health probe sees it."""

    status: str
    database: str
    version: str
    #: The commit the running image was built from, when it was built by CI.
    revision: str | None


def health_router(
    check_database: Callable[[Request], Awaitable[None]],
    *,
    version: str,
    revision: str | None = None,
) -> APIRouter:
    """A router with ``GET /health``, unauthenticated, that asks the database before answering.

    ``check_database`` runs a trivial query (``SELECT 1``) and raises when the database cannot
    answer. A process that answers while its database is unreachable is not healthy, so that is
    a 503 with ``database: unreachable``; ``python -m jigkit.healthcheck URL --expect
    database=connected`` then fails either way.
    """
    router = APIRouter(tags=["health"])

    @router.get("/health", response_model=Health, responses={503: {"model": Health}})
    async def health(request: Request) -> Health | JSONResponse:
        """Report that the process is up and its database answers."""
        try:
            await check_database(request)
        except Exception:
            logger.exception("health check: the database did not answer")
            down = Health(
                status="error", database="unreachable", version=version, revision=revision
            )
            return JSONResponse(down.model_dump(), status_code=503)
        return Health(status="ok", database="connected", version=version, revision=revision)

    return router
