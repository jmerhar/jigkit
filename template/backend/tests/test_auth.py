"""First-run setup, logging in and out, and the browsers logged in."""

import asyncio

import httpx
from conftest import PASSWORD


async def test_setup_is_needed_until_someone_exists(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/setup")).json() == {"required": True}

    response = await client.post(
        "/api/setup",
        json={"name": " Ana ", "login": " ANA ", "password": PASSWORD, "language": "pt-PT"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Ana",
        "login": "ana",
        "language": "pt-PT",
        "notifications": True,
    }
    assert (await client.get("/api/auth/me")).json()["login"] == "ana"
    assert (await client.get("/api/setup")).json() == {"required": False}


async def test_setup_is_closed_once_done(client, user, new_client) -> None:
    async with new_client() as other:
        response = await other.post(
            "/api/setup", json={"name": "B", "login": "b", "password": PASSWORD}
        )

    assert (response.status_code, response.json()["detail"]) == (409, "already_set_up")


async def test_two_setups_at_once_make_one_account(new_client) -> None:
    body = {"name": "A", "login": "a", "password": PASSWORD}
    async with new_client() as first, new_client() as second:
        answers = await asyncio.gather(
            first.post("/api/setup", json=body), second.post("/api/setup", json=body)
        )

    assert sorted(answer.status_code for answer in answers) == [201, 409]


async def test_setup_wants_a_long_password_and_a_known_language(client: httpx.AsyncClient) -> None:
    short = await client.post("/api/setup", json={"name": "A", "login": "a", "password": "short"})
    assert (short.status_code, short.json()["detail"]) == (422, "password_too_short")

    made = await client.post(
        "/api/setup", json={"name": "A", "login": "a", "password": PASSWORD, "language": "klingon"}
    )
    assert made.json()["language"] is None


async def test_logging_in_and_out(user, new_client) -> None:
    async with new_client() as browser:
        assert (await browser.get("/api/auth/me")).status_code == 401
        response = await browser.post(
            "/api/auth/login", json={"login": "ANA", "password": PASSWORD}
        )
        assert response.status_code == 200
        assert (await browser.get("/api/auth/me")).json()["name"] == "Ana"

        assert (await browser.post("/api/auth/logout")).status_code == 204
        assert (await browser.get("/api/auth/me")).status_code == 401
        assert (await browser.post("/api/auth/logout")).status_code == 204


async def test_a_wrong_password_or_unknown_login_is_refused_alike(user, new_client) -> None:
    async with new_client() as browser:
        wrong = await browser.post(
            "/api/auth/login", json={"login": "ana", "password": "wrong password"}
        )
        nobody = await browser.post("/api/auth/login", json={"login": "bea", "password": PASSWORD})

    for response in (wrong, nobody):
        assert (response.status_code, response.json()["detail"]) == (401, "invalid_login")


async def test_too_many_failures_block_the_address(user, settings, new_client) -> None:
    async with new_client() as browser:
        for _ in range(settings.login_attempts_per_minute):
            await browser.post(
                "/api/auth/login", json={"login": "ana", "password": "wrong password"}
            )
        response = await browser.post(
            "/api/auth/login", json={"login": "ana", "password": PASSWORD}
        )

    assert (response.status_code, response.json()["detail"]) == (429, "too_many_attempts")


async def test_another_browser_can_be_logged_out(client, user, new_client) -> None:
    async with new_client() as phone:
        await phone.post("/api/auth/login", json={"login": "ana", "password": PASSWORD})
        sessions = (await client.get("/api/auth/sessions")).json()
        assert [session["current"] for session in sessions].count(True) == 1
        other = next(session for session in sessions if not session["current"])

        assert (await client.delete(f"/api/auth/sessions/{other['id']}")).status_code == 204
        assert (await phone.get("/api/auth/me")).status_code == 401
        assert (await client.delete(f"/api/auth/sessions/{other['id']}")).status_code == 404
