"""Serving a built single-page application from the API process."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

#: Built assets carry a content hash in their names, so a browser may keep them for good.
IMMUTABLE = "public, max-age=31536000, immutable"


def mount_spa(app: FastAPI, directory: Path | None, *, api_prefix: str = "/api") -> bool:
    """Serve the built app in ``directory``, and return whether there was one to serve.

    Absent -- no directory, or no ``index.html`` in it, as in a development stack where the
    frontend's own server serves the app and proxies the API -- the application is the API
    alone. Call this after every other route is registered: its catch-all answers any path that
    nothing else matched.

    - ``/assets/*`` is served with an immutable cache lifetime; ``assets/`` may be missing.
    - A path naming a file of the build serves it, confined to the build directory.
    - Any other path gets ``index.html`` with ``Cache-Control: no-cache``, so client-side routes
      work and a new release is picked up on the next load.
    - A path under ``api_prefix`` that matched no route is a 404, not the shell, so a mistyped
      endpoint fails loudly.
    """
    if directory is None or not (directory / "index.html").is_file():
        logger.info("no built frontend at %s; serving the API only", directory)
        return False
    root = directory.resolve()
    index = root / "index.html"
    api = api_prefix.strip("/")

    @app.middleware("http")
    async def cache_assets(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = IMMUTABLE
        return response

    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        """A file of the built app if there is one, and the app's shell otherwise."""
        if path == api or path.startswith(f"{api}/"):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if path and root in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True
