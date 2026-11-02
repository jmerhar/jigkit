"""TickLoop: ticks on an interval, survives a failing tick, starts and stops cleanly."""

from __future__ import annotations

import asyncio
import logging

import pytest

from jigkit.scheduler import TickLoop


class Ticks:
    """Counts ticks, failing on the ones it is told to."""

    def __init__(self, failing: set[int] | None = None) -> None:
        self.count = 0
        self.failing = failing or set()

    async def __call__(self) -> None:
        self.count += 1
        if self.count in self.failing:
            raise RuntimeError(f"tick {self.count} failed")


async def instant(_: float) -> None:
    """A sleep that only yields, so ticks follow each other at once."""
    await asyncio.sleep(0)


async def until(condition, timeout: float = 5.0) -> None:  # noqa: ANN001
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0)


async def test_ticks_until_stopped() -> None:
    ticks = Ticks()
    loop = TickLoop(ticks, 60, sleep=instant)

    loop.start()
    assert loop.running
    await until(lambda: ticks.count >= 3)
    await loop.stop()

    assert not loop.running
    stopped_at = ticks.count
    await asyncio.sleep(0)
    assert ticks.count == stopped_at


async def test_waits_the_interval_between_ticks() -> None:
    pauses: list[float] = []

    async def record(seconds: float) -> None:
        pauses.append(seconds)
        await asyncio.sleep(0)

    loop = TickLoop(Ticks(), 42.5, sleep=record)
    loop.start()
    await until(lambda: len(pauses) >= 2)
    await loop.stop()

    assert set(pauses) == {42.5}


async def test_a_failing_tick_is_logged_and_the_loop_carries_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ticks = Ticks(failing={1})
    loop = TickLoop(ticks, 60, name="housekeeping", sleep=instant)

    with caplog.at_level(logging.ERROR, logger="jigkit.scheduler"):
        loop.start()
        await until(lambda: ticks.count >= 2)
        await loop.stop()

    assert "housekeeping tick failed" in caplog.text


async def test_disabled_it_never_starts(caplog: pytest.LogCaptureFixture) -> None:
    ticks = Ticks()
    loop = TickLoop(ticks, 60, enabled=False, sleep=instant)

    with caplog.at_level(logging.INFO, logger="jigkit.scheduler"):
        loop.start()
    await asyncio.sleep(0)

    assert not loop.running
    assert ticks.count == 0
    assert "disabled by configuration" in caplog.text


async def test_starting_twice_runs_one_loop_and_stopping_twice_is_harmless() -> None:
    ticks = Ticks()
    loop = TickLoop(ticks, 60, sleep=instant)

    loop.start()
    first = loop._task
    loop.start()

    assert loop._task is first
    await loop.stop()
    await loop.stop()
