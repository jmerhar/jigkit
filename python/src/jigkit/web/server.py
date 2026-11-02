"""Running an application with uvicorn, the way every application built on jigkit runs."""

from __future__ import annotations

from typing import Any

import uvicorn

from jigkit.settings import AppSettings

#: Inside the container; the compose file decides what the host publishes.
HOST = "0.0.0.0"  # noqa: S104
PORT = 8000


def serve(
    factory: str,
    settings: AppSettings,
    *,
    reload: bool = False,
    host: str = HOST,
    port: int = PORT,
    **uvicorn_options: Any,
) -> None:
    """Serve the application ``factory`` builds, an import string such as ``myapp.api:create_app``.

    - The logging the application configured is kept (``log_config=None``) instead of
      uvicorn's own handlers replacing it.
    - X-Forwarded-For and X-Forwarded-Proto are believed only from
      ``settings.forwarded_allow_ips``: they decide the client address a login throttle counts
      and whether a session cookie is Secure, so believing them from anyone lets a client
      choose both.
    - No ``Server`` header names the server software.
    - ``reload`` restarts on source changes, for development.

    Further keyword arguments go to ``uvicorn.run``.
    """
    options: dict[str, Any] = {
        "factory": True,
        "host": host,
        "port": port,
        "log_config": None,
        "proxy_headers": True,
        "forwarded_allow_ips": settings.forwarded_allow_ips,
        "server_header": False,
        "reload": reload,
    }
    options.update(uvicorn_options)
    uvicorn.run(factory, **options)
