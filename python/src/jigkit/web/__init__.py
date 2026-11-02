"""Building blocks for a FastAPI application (extra ``web``).

Each is applied to an application the app builds itself, so an application keeps its own
factory and lifespan and takes only the pieces it wants:

- :class:`AccessPolicy`: every API route needs a credential unless it is declared open;
- :func:`install_write_guard`: writes under the API only from the application's own pages;
- :func:`install_security_headers`: nosniff, a same-origin referrer, no framing;
- :func:`mount_spa`: the built single-page app, with its client-side routes and cache headers;
- :func:`health_router`: ``/health``, which queries the database;
- :func:`web_manifest` and :func:`manifest_response`: the PWA manifest;
- :func:`serve`: uvicorn, believing forwarded headers only from the configured proxies.
"""

from jigkit.web.access import AccessPolicy, Route, route_templates
from jigkit.web.guard import (
    WRITE_HEADER,
    WRITES,
    install_security_headers,
    install_write_guard,
    origin_allowed,
)
from jigkit.web.health import Health, health_router
from jigkit.web.manifest import manifest_response, preferred_language, web_manifest
from jigkit.web.server import serve
from jigkit.web.spa import IMMUTABLE, mount_spa

__all__ = [
    "IMMUTABLE",
    "WRITES",
    "WRITE_HEADER",
    "AccessPolicy",
    "Health",
    "Route",
    "health_router",
    "install_security_headers",
    "install_write_guard",
    "manifest_response",
    "mount_spa",
    "origin_allowed",
    "preferred_language",
    "route_templates",
    "serve",
    "web_manifest",
]
