"""The FastAPI building blocks, exercised through real applications over ASGI."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

import jigkit.web.server as serve_module
from jigkit.settings import AppSettings
from jigkit.web import (
    IMMUTABLE,
    health_router,
    install_security_headers,
    install_write_guard,
    manifest_response,
    manifest_router,
    mount_spa,
    origin_allowed,
    preferred_language,
    serve,
    web_manifest,
)


async def client_for(app: FastAPI) -> httpx.AsyncClient:
    """A client talking to ``app`` in process, as if from http://testserver."""
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
async def guarded() -> AsyncIterator[httpx.AsyncClient]:
    """An application with a write guard, one API write route and one write outside the API."""
    app = FastAPI()
    install_write_guard(app, value="myapp", public_url="https://costs.example.com")

    @app.post("/api/items")
    async def create() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/api/items")
    async def read() -> dict[str, str]:
        return {"ok": "yes"}

    @app.post("/hook")
    async def hook() -> dict[str, str]:
        return {"ok": "yes"}

    async with await client_for(app) as client:
        yield client


class TestWriteGuard:
    async def test_a_write_with_the_header_passes(self, guarded: httpx.AsyncClient) -> None:
        response = await guarded.post("/api/items", headers={"X-Requested-With": "myapp"})

        assert response.status_code == 200

    @pytest.mark.parametrize("value", [None, "other"])
    async def test_a_write_without_the_header_is_refused(
        self, guarded: httpx.AsyncClient, value: str | None
    ) -> None:
        headers = {"X-Requested-With": value} if value else {}

        response = await guarded.post("/api/items", headers=headers)

        assert (response.status_code, response.json()) == (403, {"detail": "missing_write_header"})

    async def test_a_write_from_another_origin_is_refused(self, guarded: httpx.AsyncClient) -> None:
        response = await guarded.post(
            "/api/items",
            headers={"X-Requested-With": "myapp", "Origin": "https://evil.example.net"},
        )

        assert (response.status_code, response.json()) == (403, {"detail": "foreign_origin"})

    @pytest.mark.parametrize("origin", ["https://costs.example.com", "http://testserver"])
    async def test_a_write_from_its_own_origin_passes(
        self, guarded: httpx.AsyncClient, origin: str
    ) -> None:
        response = await guarded.post(
            "/api/items", headers={"X-Requested-With": "myapp", "Origin": origin}
        )

        assert response.status_code == 200

    async def test_reads_and_writes_outside_the_api_are_not_guarded(
        self, guarded: httpx.AsyncClient
    ) -> None:
        assert (await guarded.get("/api/items")).status_code == 200
        assert (await guarded.post("/hook")).status_code == 200

    @pytest.mark.parametrize(
        ("origin", "host", "public_url", "allowed"),
        [
            (None, "a.example", None, True),
            ("null", "a.example", None, False),
            ("https://a.example", "a.example", None, True),
            ("HTTP://A.EXAMPLE", "a.example", None, True),
            ("https://b.example", "a.example", "https://b.example/app", True),
            ("https://c.example", None, None, False),
        ],
    )
    def test_origin_allowed(
        self, origin: str | None, host: str | None, public_url: str | None, allowed: bool
    ) -> None:
        assert origin_allowed(origin, host, public_url) is allowed


class TestSecurityHeaders:
    async def test_every_response_gets_them(self) -> None:
        app = FastAPI()
        install_security_headers(app)

        @app.get("/page")
        async def page() -> dict[str, str]:
            return {}

        async with await client_for(app) as client:
            response = await client.get("/page")
            missing = await client.get("/nowhere")

        for answer in (response, missing):
            assert answer.headers["X-Content-Type-Options"] == "nosniff"
            assert answer.headers["Referrer-Policy"] == "same-origin"
            assert answer.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
            assert answer.headers["X-Frame-Options"] == "DENY"

    async def test_a_response_keeps_a_header_it_set_itself(self) -> None:
        app = FastAPI()
        install_security_headers(app)

        @app.get("/document")
        async def document() -> PlainTextResponse:
            return PlainTextResponse("x", headers={"Content-Security-Policy": "sandbox"})

        async with await client_for(app) as client:
            response = await client.get("/document")

        assert response.headers["Content-Security-Policy"] == "sandbox"


@pytest.fixture
def build(tmp_path: Path) -> Path:
    """A built single-page app: a shell, a hashed asset and a top-level file."""
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>shell</html>")
    (root / "assets" / "app-1a2b.js").write_text("console.log(1)")
    (root / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("outside the build")
    return root


def spa_app(directory: Path | None) -> tuple[FastAPI, bool]:
    """An application with one API route and the built app mounted after it."""
    app = FastAPI()

    @app.get("/api/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "yes"}

    return app, mount_spa(app, directory)


class TestSpa:
    async def test_client_side_routes_get_the_shell_uncached(self, build: Path) -> None:
        app, mounted = spa_app(build)

        async with await client_for(app) as client:
            root = await client.get("/")
            route = await client.get("/bills/2026")

        assert mounted
        for response in (root, route):
            assert response.text == "<html>shell</html>"
            assert response.headers["Cache-Control"] == "no-cache"

    async def test_assets_are_cached_for_good(self, build: Path) -> None:
        app, _ = spa_app(build)

        async with await client_for(app) as client:
            response = await client.get("/assets/app-1a2b.js")

        assert response.status_code == 200
        assert response.headers["Cache-Control"] == IMMUTABLE

    async def test_a_missing_asset_is_not_cached(self, build: Path) -> None:
        app, _ = spa_app(build)

        async with await client_for(app) as client:
            response = await client.get("/assets/gone.js")

        assert response.status_code == 404
        assert response.headers.get("Cache-Control") != IMMUTABLE

    async def test_a_file_of_the_build_is_served(self, build: Path) -> None:
        app, _ = spa_app(build)

        async with await client_for(app) as client:
            response = await client.get("/favicon.svg")

        assert response.text == "<svg/>"

    async def test_nothing_outside_the_build_is_reachable(self, build: Path) -> None:
        app, _ = spa_app(build)

        async with await client_for(app) as client:
            response = await client.get("/%2e%2e/secret.txt")

        assert "outside the build" not in response.text

    @pytest.mark.parametrize("path", ["/api", "/api/nothing"])
    async def test_an_unknown_api_path_is_a_404_not_the_shell(self, build: Path, path: str) -> None:
        app, _ = spa_app(build)

        async with await client_for(app) as client:
            response = await client.get(path)
            ping = await client.get("/api/ping")

        assert response.status_code == 404
        assert ping.json() == {"pong": "yes"}

    async def test_a_build_without_assets_still_serves(self, build: Path) -> None:
        for asset in (build / "assets").iterdir():
            asset.unlink()
        (build / "assets").rmdir()
        app, mounted = spa_app(build)

        async with await client_for(app) as client:
            response = await client.get("/")

        assert mounted
        assert response.text == "<html>shell</html>"

    @pytest.mark.parametrize("directory", [None, Path("/nonexistent/dist")])
    def test_without_a_build_only_the_api_is_served(self, directory: Path | None) -> None:
        app, mounted = spa_app(directory)

        assert not mounted
        assert not any(getattr(r, "path", "") == "/{path:path}" for r in app.routes)


class TestHealth:
    @staticmethod
    def app(failing: bool) -> FastAPI:
        async def check(request: Request) -> None:
            assert isinstance(request, Request)
            if failing:
                raise RuntimeError("database is locked")

        app = FastAPI()
        app.include_router(health_router(check, version="1.2.3", revision="abc123"), prefix="/api")
        return app

    async def test_healthy_when_the_database_answers(self) -> None:
        async with await client_for(self.app(failing=False)) as client:
            response = await client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "database": "connected",
            "version": "1.2.3",
            "revision": "abc123",
        }

    async def test_a_503_when_the_database_does_not(self, caplog: pytest.LogCaptureFixture) -> None:
        async with await client_for(self.app(failing=True)) as client:
            response = await client.get("/api/health")

        assert response.status_code == 503
        assert response.json()["database"] == "unreachable"
        assert "database is locked" in caplog.text


class TestManifest:
    def test_a_manifest_lists_its_icons_and_colours(self) -> None:
        manifest = web_manifest(
            name="My app",
            description="Does things",
            lang="en",
            background_color="#ffffff",
            theme_color="#123456",
        )

        assert manifest["short_name"] == "My app"
        assert manifest["display"] == "standalone"
        icons: Any = manifest["icons"]
        assert [(i["sizes"], i["purpose"]) for i in icons] == [
            ("192x192", "any"),
            ("512x512", "any"),
            ("512x512", "maskable"),
        ]
        assert icons[0]["src"] == "/icons/icon-192.png"

    def test_the_response_varies_by_language_and_is_rechecked(self) -> None:
        response = manifest_response(
            web_manifest(
                name="App",
                short_name="A",
                description="d",
                lang="pt-PT",
                background_color="#fff",
                theme_color="#000",
            )
        )

        assert response.media_type == "application/manifest+json"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Content-Language"] == "pt-PT"
        assert response.headers["Vary"] == "Accept-Language"

    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("pt-BR,pt;q=0.9,en;q=0.8", "pt-PT"),
            ("en-GB,en;q=0.9", "en"),
            ("de-DE, , pt", "pt-PT"),
            ("de-DE", "en"),
            (None, "en"),
        ],
    )
    def test_preferred_language(self, header: str | None, expected: str) -> None:
        assert preferred_language(header, ["en", "pt-PT"], "en") == expected

    WORDS = {"en": ("My app", "Does things"), "pt-PT": ("A minha app", "Faz coisas")}

    async def test_the_route_answers_in_the_browsers_language_without_a_login(self) -> None:
        app = FastAPI()
        app.include_router(manifest_router(self.WORDS, background_color="#fff", theme_color="#000"))

        async with await client_for(app) as client:
            portuguese = await client.get(
                "/manifest.webmanifest", headers={"Accept-Language": "pt"}
            )
            other = await client.get("/manifest.webmanifest", headers={"Accept-Language": "de"})

        assert portuguese.status_code == 200
        assert portuguese.headers["content-type"] == "application/manifest+json"
        assert portuguese.json()["name"] == "A minha app"
        assert portuguese.json()["description"] == "Faz coisas"
        assert other.json()["lang"] == "en"
        assert other.json()["theme_color"] == "#000"
        assert "/manifest.webmanifest" not in app.openapi()["paths"]

    @pytest.mark.parametrize(
        ("chosen", "expected"),
        [("  Main Street 1 ", "Main Street 1"), (" ", "Mine"), (None, "Mine")],
    )
    async def test_a_chosen_name_replaces_the_words_unless_blank(
        self, chosen: str | None, expected: str
    ) -> None:
        async def name(request: Request) -> str | None:
            return chosen

        app = FastAPI()
        app.include_router(
            manifest_router(
                {"nl": ("Mine", "d"), "en": ("Mine", "d")},
                background_color="#fff",
                theme_color="#000",
                default="en",
                name=name,
                icon="/static/{size}.png",
            )
        )

        async with await client_for(app) as client:
            manifest = (await client.get("/manifest.webmanifest")).json()

        assert manifest["name"] == manifest["short_name"] == expected
        assert manifest["lang"] == "en"
        assert manifest["icons"][0]["src"] == "/static/192.png"

    def test_the_route_needs_a_language(self) -> None:
        with pytest.raises(ValueError, match="at least one language"):
            manifest_router({}, background_color="#fff", theme_color="#000")


class TestServe:
    @pytest.fixture
    def runs(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
        calls: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(
            serve_module.uvicorn, "run", lambda app, **options: calls.append((app, options))
        )
        return calls

    def test_serves_the_factory_trusting_only_the_configured_proxies(
        self, runs: list[tuple[str, dict[str, Any]]]
    ) -> None:
        serve("myapp.api:create_app", AppSettings(forwarded_allow_ips="172.18.0.1"))

        ((app, options),) = runs
        assert app == "myapp.api:create_app"
        assert options == {
            "factory": True,
            "host": "0.0.0.0",
            "port": 8000,
            "log_config": None,
            "proxy_headers": True,
            "forwarded_allow_ips": "172.18.0.1",
            "server_header": False,
            "reload": False,
        }

    def test_options_can_be_added_or_changed(self, runs: list[tuple[str, dict[str, Any]]]) -> None:
        serve("myapp:create", AppSettings(), reload=True, port=9000, limit_concurrency=64)

        ((_, options),) = runs
        assert (options["reload"], options["port"], options["limit_concurrency"]) == (
            True,
            9000,
            64,
        )
