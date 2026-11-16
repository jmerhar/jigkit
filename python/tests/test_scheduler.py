"""Schedule and TickLoop: what is due runs, failures are reported, and the loops stop cleanly."""

from __future__ import annotations

import asyncio
import logging

import pytest

from jigkit.scheduler import Job, LoggingReporter, Schedule, TickLoop, wait_or_wake


class Stop(Exception):
    """Ends a schedule's run in a test."""


class Harness:
    """A reporter whose clock moves only when the schedule sleeps, or when a job says so."""

    name = "src"

    def __init__(self, rounds: int = 3) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []
        self.problems: list[str] = []
        self.successes = 0
        self.ran: list[tuple[str, float]] = []
        self.rounds = rounds

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if len(self.sleeps) >= self.rounds:
            raise Stop
        # Waits a moment first, as a real sleep does, so a wake-up can cut it short.
        await asyncio.sleep(0.01)
        self.now += seconds

    def succeeded(self) -> None:
        self.successes += 1

    def problem(self, message: str) -> None:
        self.problems.append(message)

    def job(self, name: str, *, takes: float = 0.0, result=None, error=None):  # noqa: ANN001, ANN201
        """A job that records when it ran, takes ``takes`` seconds, then fails or returns."""

        async def run():  # noqa: ANN202
            self.ran.append((name, self.now))
            self.now += takes
            if error is not None:
                raise error
            return result

        return run


async def run(schedule: Schedule) -> None:
    with pytest.raises(Stop):
        await schedule.run()


class TestSchedule:
    def test_needs_jobs_with_distinct_names(self) -> None:
        harness = Harness()
        with pytest.raises(ValueError, match="distinct names"):
            Schedule(harness, [])
        job = Job("a", 1, harness.job("a"))
        with pytest.raises(ValueError, match="distinct names"):
            Schedule(harness, [job, job])

    async def test_every_job_runs_at_the_start_then_when_due(self) -> None:
        harness = Harness(rounds=4)
        await run(
            Schedule(
                harness,
                [Job("fast", 10, harness.job("fast")), Job("slow", 25, harness.job("slow"))],
            )
        )

        assert harness.ran == [
            ("fast", 1000),
            ("slow", 1000),
            ("fast", 1010),
            ("fast", 1020),
            ("slow", 1025),
        ]
        assert harness.sleeps == [10, 10, 5, 5]
        assert harness.successes == 4 and harness.problems == []

    async def test_the_interval_runs_from_the_start_and_an_overrun_runs_again_at_once(self) -> None:
        harness = Harness(rounds=3)
        takes = iter([4.0, 12.0, 1.0])

        async def work() -> None:
            harness.ran.append(("work", harness.now))
            harness.now += next(takes)

        await run(Schedule(harness, [Job("work", 10, work)]))

        # The overrun round started at 1010 and ended at 1022, so the next one starts at once
        # and the one after is due at 1032, 9 s after it ended.
        assert harness.sleeps == [6.0, 0.0, 9.0]
        assert harness.ran == [("work", 1000), ("work", 1010), ("work", 1022)]

    async def test_a_failure_is_reported_and_the_other_jobs_still_run(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        harness = Harness(rounds=1)
        with caplog.at_level(logging.DEBUG, logger="jigkit.scheduler"):
            await run(
                Schedule(
                    harness,
                    [
                        Job("broken", 10, harness.job("broken", error=TimeoutError())),
                        Job("fine", 10, harness.job("fine")),
                    ],
                )
            )

        assert [name for name, _ in harness.ran] == ["broken", "fine"]
        # A timeout's message is empty, so its type names it; with two jobs, the job is named.
        assert harness.problems == ["broken: TimeoutError"]
        assert harness.successes == 0
        assert "src: broken: TimeoutError" in caplog.text
        # The traceback is there for whoever turns on debug logging.
        assert any(record.exc_info for record in caplog.records)

    async def test_a_single_job_s_failure_is_not_prefixed_and_a_later_round_succeeds(self) -> None:
        harness = Harness(rounds=2)
        outcomes = iter([ValueError("bad answer"), None])

        async def poll() -> None:
            if (outcome := next(outcomes)) is not None:
                raise outcome

        await run(Schedule(harness, [Job("poll", 60, poll)]))

        assert harness.problems == ["bad answer"]
        assert harness.successes == 1

    async def test_a_job_that_reports_its_own_problem_returns_false(self) -> None:
        harness = Harness(rounds=2)
        await run(Schedule(harness, [Job("j", 5, harness.job("j", result=False))]))

        assert harness.successes == 0 and harness.problems == []

    async def test_a_job_can_move_its_next_run(self) -> None:
        harness = Harness(rounds=2)
        schedule: Schedule

        async def backlog() -> None:
            schedule.due_in("backlog", 3)

        schedule = Schedule(harness, [Job("backlog", 900, backlog)])
        await run(schedule)

        assert harness.sleeps == [3, 3]

    async def test_a_wake_up_runs_the_jobs_marked_for_it_at_once(self) -> None:
        harness = Harness(rounds=2)
        woken = asyncio.Event()

        async def scan() -> None:
            harness.ran.append(("scan", harness.now))
            if len(harness.ran) == 1:
                # Woken while it runs, as by an upload: it runs again without waiting its turn.
                woken.set()

        jobs = [Job("scan", 600, scan, on_wake=True), Job("other", 600, harness.job("other"))]
        await run(Schedule(harness, jobs, wake=woken))

        assert harness.ran == [("scan", 1000), ("other", 1000), ("scan", 1000)]
        assert harness.sleeps == [600.0, 600.0]

    async def test_wait_or_wake_returns_when_woken_or_when_the_time_is_up(self) -> None:
        harness = Harness(rounds=10)
        woken = asyncio.Event()
        woken.set()
        await wait_or_wake(harness, woken, 300)
        woken.clear()
        await wait_or_wake(harness, woken, 5)

        assert harness.now == 1005

    async def test_a_logging_reporter_needs_nothing_but_a_name(self) -> None:
        reporter = LoggingReporter("feeds")
        ran: list[str] = []

        async def job() -> None:
            ran.append("job")

        schedule = Schedule(reporter, [Job("job", 60, job)])
        await schedule.round()
        reporter.problem("ignored")

        assert ran == ["job"]
        assert reporter.name == "feeds"


class Ticks:
    """Counts ticks, failing on the ones it is told to."""

    def __init__(self, failing: set[int] | None = None) -> None:
        self.count = 0
        self.failing = failing or set()

    async def __call__(self) -> None:
        self.count += 1
        if self.count in self.failing:
            raise RuntimeError(f"tick {self.count} failed")


class Clock:
    """A clock that a sleep moves on, so ticks follow each other at once."""

    def __init__(self) -> None:
        self.now = 0.0
        self.pauses: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.pauses.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)


async def until(condition, timeout: float = 5.0) -> None:  # noqa: ANN001
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0)


class TestTickLoop:
    async def test_ticks_until_stopped(self) -> None:
        ticks, clock = Ticks(), Clock()
        loop = TickLoop(ticks, 60, clock=clock, sleep=clock.sleep)

        loop.start()
        assert loop.running
        await until(lambda: ticks.count >= 3)
        await loop.stop()

        assert not loop.running
        stopped_at = ticks.count
        await asyncio.sleep(0)
        assert ticks.count == stopped_at

    async def test_ticks_every_interval_from_when_a_tick_started(self) -> None:
        clock = Clock()

        async def slow() -> None:
            clock.now += 2.5

        loop = TickLoop(slow, 42.5, clock=clock, sleep=clock.sleep)
        loop.start()
        await until(lambda: len(clock.pauses) >= 2)
        await loop.stop()

        assert set(clock.pauses) == {40.0}

    async def test_a_failing_tick_is_logged_and_the_loop_carries_on(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ticks, clock = Ticks(failing={1}), Clock()
        loop = TickLoop(ticks, 60, name="housekeeping", clock=clock, sleep=clock.sleep)

        with caplog.at_level(logging.ERROR, logger="jigkit.scheduler"):
            loop.start()
            await until(lambda: ticks.count >= 2)
            await loop.stop()

        assert "housekeeping tick failed" in caplog.text
        assert any(record.exc_info for record in caplog.records)

    async def test_disabled_it_never_starts(self, caplog: pytest.LogCaptureFixture) -> None:
        ticks = Ticks()
        loop = TickLoop(ticks, 60, enabled=False)

        with caplog.at_level(logging.INFO, logger="jigkit.scheduler"):
            loop.start()
        await asyncio.sleep(0)

        assert not loop.running
        assert ticks.count == 0
        assert "disabled by configuration" in caplog.text

    async def test_starting_twice_runs_one_loop_and_stopping_twice_is_harmless(self) -> None:
        clock = Clock()
        loop = TickLoop(Ticks(), 60, clock=clock, sleep=clock.sleep)

        loop.start()
        first = loop._task
        loop.start()

        assert loop._task is first
        await loop.stop()
        await loop.stop()
