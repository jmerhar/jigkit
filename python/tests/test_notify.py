"""Notifications through Apprise, delivered to a real local stand-in server."""

from __future__ import annotations

import json
import logging

import pytest

from jigkit.notify import AppriseSender, redact_url
from jigkit.testing.http import StubServer, serving
from jigkit.testing.notify import RecordingSender, Sent


async def test_a_message_reaches_its_destination() -> None:
    async with serving(StubServer(status=200)) as stub:
        url = stub.url.replace("http://", "json://") + "/notify"

        assert await AppriseSender().send([url], "Title", "Body text") is True

    (request,) = stub.requests
    assert request.method == "POST"
    assert request.path == "/notify"
    payload = json.loads(request.body)
    assert (payload["title"], payload["message"]) == ("Title", "Body text")


async def test_a_refusing_destination_reports_failure() -> None:
    async with serving(StubServer(status=500)) as stub:
        url = stub.url.replace("http://", "json://")

        assert await AppriseSender().send([url], "Title", "Body") is False


async def test_no_usable_destination_sends_nothing_and_warns_without_the_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="jigkit.notify"):
        sent = await AppriseSender().send(["nosuchscheme://token-s3cr3t-1234"], "T", "B")

    assert sent is False
    assert "did not recognise a destination" in caplog.text
    assert "s3cr3t" not in caplog.text


async def test_no_destinations_at_all_is_not_a_success() -> None:
    assert await AppriseSender().send([], "T", "B") is False


@pytest.mark.parametrize(
    ("url", "shown"),
    [
        ("tgram://123456:ABCDEFtoken/987654", "tgram://…7654"),
        ("mailtos://user:password@example.com", "mailtos://….com"),
        ("ntfy://short", "ntfy://…"),
        ("json://", "json://…"),
        ("no scheme at all", "<malformed url>"),
    ],
)
def test_redact_url_keeps_only_the_scheme_and_a_tail(url: str, shown: str) -> None:
    assert redact_url(url) == shown


async def test_the_recording_sender_keeps_what_it_was_given() -> None:
    sender = RecordingSender(accept=False)

    assert await sender.send(["json://a"], "Title", "Body") is False
    assert sender.sent == [Sent(["json://a"], "Title", "Body")]
