"""The fail-closed access policy, applied to a real application over ASGI."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request

from jigkit.web.access import AccessPolicy, route_templates

OPEN = {
    ("GET", "/api/health"),
    ("get", "/api/items/{item_id}"),
    ("POST", "/api/auth/login"),
}


def logged_in(request: Request) -> bool:
    """The credential in these tests: a header naming the right key."""
    return request.headers.get("x-key") == "letmein"


async def logged_in_async(request: Request) -> bool:
    return logged_in(request)


def build(allow: Callable[[Request], bool | Awaitable[bool]], **options) -> FastAPI:
    """An application with a nested router under /api, guarded by the policy."""
    items = APIRouter(prefix="/items")

    @items.get("/{item_id}")
    async def read(item_id: int) -> dict[str, int]:
        return {"id": item_id}

    @items.get("/{item_id}/secret")
    async def secret(item_id: int) -> dict[str, int]:
        return {"secret": item_id}

    @items.post("/{item_id}")
    async def write(item_id: int) -> dict[str, int]:
        return {"written": item_id}

    api = APIRouter()
    api.include_router(items)

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/auth/login")
    async def login() -> dict[str, str]:
        return {}

    @api.get("/hidden", include_in_schema=False)
    async def hidden() -> dict[str, str]:
        return {}

    app = FastAPI()
    policy = AccessPolicy(OPEN, allow=allow, prefix="/api/", **options)
    app.include_router(api, prefix="/api", dependencies=[Depends(policy)])
    app.state.policy = policy
    return app


@pytest.fixture(params=[logged_in, logged_in_async], ids=["sync", "async"])
async def client(request: pytest.FixtureRequest) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=build(request.param))
    async with httpx.AsyncClient(transport=transport, base_url="http://app.test") as client:
        yield client


class TestEnforcement:
    @pytest.mark.parametrize(
        ("method", "path"),
        [("GET", "/api/health"), ("GET", "/api/items/3"), ("POST", "/api/auth/login")],
    )
    async def test_open_routes_need_nothing(
        self, client: httpx.AsyncClient, method: str, path: str
    ) -> None:
        assert (await client.request(method, path)).status_code == 200

    @pytest.mark.parametrize(
        ("method", "path"),
        [("POST", "/api/items/3"), ("GET", "/api/items/3/secret"), ("GET", "/api/hidden")],
    )
    async def test_every_other_route_needs_the_credential(
        self, client: httpx.AsyncClient, method: str, path: str
    ) -> None:
        refused = await client.request(method, path)
        allowed = await client.request(method, path, headers={"x-key": "letmein"})

        assert (refused.status_code, refused.json()) == (403, {"detail": "forbidden"})
        assert allowed.status_code == 200

    async def test_a_wrong_credential_is_refused(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/items/3", headers={"x-key": "guess"})

        assert response.status_code == 403

    async def test_an_unknown_path_is_a_404(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/nowhere")).status_code == 404

    async def test_the_refusal_can_be_chosen(self) -> None:
        app = build(logged_in, status_code=401, detail="login_required")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://app.test") as client:
            response = await client.post("/api/items/3")

        assert (response.status_code, response.json()) == (401, {"detail": "login_required"})

    async def test_a_request_without_a_matched_route_needs_the_credential(self) -> None:
        policy = AccessPolicy(OPEN, allow=logged_in)
        scope = {"type": "http", "method": "GET", "path": "/api/health", "headers": []}

        with pytest.raises(HTTPException, match="forbidden"):
            await policy(Request(scope))
        await policy(Request({**scope, "headers": [(b"x-key", b"letmein")]}))


class TestDeclarations:
    def test_route_templates_are_full_paths_with_their_methods(self) -> None:
        assert route_templates(build(logged_in)) == {
            ("GET", "/api/health"),
            ("POST", "/api/auth/login"),
            ("GET", "/api/items/{item_id}"),
            ("POST", "/api/items/{item_id}"),
            ("GET", "/api/items/{item_id}/secret"),
        }

    def test_declarations_are_matched_by_either_reading_of_a_routes_path(self) -> None:
        policy = AccessPolicy(OPEN, allow=logged_in, prefix="/api")

        assert policy.is_open("GET", "/api/health")
        assert policy.is_open("get", "/health")
        assert not policy.is_open("POST", "/health")
        assert not policy.is_open("GET", "/items/{item_id}/secret")

    def test_open_routes_the_application_does_not_serve_are_reported(self) -> None:
        app = build(logged_in)
        policy: AccessPolicy = app.state.policy

        assert policy.unknown(app) == set()
        typo = AccessPolicy({*OPEN, ("GET", "/api/helth")}, allow=logged_in)
        assert typo.unknown(app) == {("GET", "/api/helth")}
