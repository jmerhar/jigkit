"""The logged-in user's own account."""

import httpx
from conftest import NOTIFY_URL, PASSWORD
from jigkit.testing.notify import RecordingSender


async def test_the_name_and_language_can_be_changed(client: httpx.AsyncClient, user) -> None:
    response = await client.put("/api/account", json={"name": "Ana Silva", "language": "pt-PT"})

    assert response.json()["name"] == "Ana Silva" and response.json()["language"] == "pt-PT"
    cleared = await client.put("/api/account", json={"name": "Ana", "language": "xx"})
    assert cleared.json()["language"] is None


async def test_a_new_password_logs_out_every_other_browser(client, user, new_client) -> None:
    async with new_client() as phone:
        await phone.post("/api/auth/login", json={"login": "ana", "password": PASSWORD})
        wrong = await client.put(
            "/api/account/password", json={"current": "nope", "new": "a new password"}
        )
        short = await client.put(
            "/api/account/password", json={"current": PASSWORD, "new": "short"}
        )
        changed = await client.put(
            "/api/account/password", json={"current": PASSWORD, "new": "a new password"}
        )

        assert (wrong.status_code, wrong.json()["detail"]) == (403, "wrong_password")
        assert (short.status_code, short.json()["detail"]) == (422, "password_too_short")
        assert changed.status_code == 204
        assert (await phone.get("/api/auth/me")).status_code == 401
        assert (await client.get("/api/auth/me")).status_code == 200


async def test_a_test_notification_goes_to_the_configured_url(
    client: httpx.AsyncClient, user, sender: RecordingSender
) -> None:
    assert (await client.post("/api/account/test-notification")).status_code == 204

    (sent,) = sender.sent
    assert sent.urls == [NOTIFY_URL] and "Ana" in sent.body


async def test_a_notification_that_fails_says_so(client, user, sender: RecordingSender) -> None:
    sender.accept = False
    response = await client.post("/api/account/test-notification")

    assert (response.status_code, response.json()["detail"]) == (502, "notification_failed")


async def test_without_a_url_there_is_nothing_to_send(client, user, settings) -> None:
    settings.notify_url = None
    me = (await client.get("/api/auth/me")).json()
    response = await client.post("/api/account/test-notification")

    assert me["notifications"] is False
    assert (response.status_code, response.json()["detail"]) == (404, "notifications_off")
