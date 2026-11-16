"""Work an application does on its own, on a timer, inside its own process.

A plain asyncio loop rather than a scheduling library: scheduled work is "do whatever is due",
and a round of it is a method call a test can drive directly instead of waiting for.

- :class:`Schedule` runs several :class:`Job` objects, each on its own interval, reporting each
  job's failures to a :class:`Reporter` and carrying on with the others; an event can wake the
  jobs that should run at once, such as an import after an upload.
- :class:`TickLoop` calls one function on a fixed tick between :meth:`~TickLoop.start` and
  :meth:`~TickLoop.stop`: the shape for work whose "is it due?" an application keeps in its own
  data, such as a daily job that must not run twice after a restart.

An interval is counted from when a job started, so it holds however long the job takes, and a
job that overran its interval runs again at once.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class Reporter(Protocol):
    """Where a :class:`Schedule` keeps time and reports how its rounds went."""

    #: The name its failures are logged under.
    name: str

    def clock(self) -> float:
        """The time now, in seconds; only differences between readings are used."""
        ...

    async def sleep(self, seconds: float) -> None:
        """Wait ``seconds``."""
        ...

    def succeeded(self) -> None:
        """A round in which every job that ran succeeded."""
        ...

    def problem(self, message: str) -> None:
        """A job failed, for the reason ``message`` gives."""
        ...


class LoggingReporter:
    """A :class:`Reporter` that logs each failure, on the monotonic clock and asyncio's sleep."""

    def __init__(
        self,
        name: str,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.name = name
        self.clock = clock
        self.sleep = sleep

    def succeeded(self) -> None:
        """Nothing to report: :class:`Schedule` has already done the work."""

    def problem(self, message: str) -> None:
        """Nothing beyond the warning :class:`Schedule` logs for every failure."""


@dataclass(frozen=True)
class Job:
    """Work done every ``every`` seconds. ``run`` returns False when it reported its own problem;
    anything else is a success."""

    name: str
    every: float
    run: Callable[[], Awaitable[bool | None]]
    #: Whether setting the schedule's ``wake`` event runs it at once.
    on_wake: bool = False


class Schedule:
    """Runs jobs when they are due, for ever.

    Every job is due at the start. A round runs each due job in the order given, then the
    schedule sleeps until the next one is due. A job is next due ``every`` seconds after it
    started; it can move its own next run with :meth:`due_in`, such as sooner while it has a
    backlog.

    A job that raises is reported through the reporter (prefixed with its name when the schedule
    has more than one) and logged, and runs again when next due: one failing job is no reason to
    stop the others. A round in which every job that ran succeeded is reported as a success.

    With ``wake``, setting the event runs the jobs marked ``on_wake`` at once instead of at their
    next turn.
    """

    def __init__(
        self, reporter: Reporter, jobs: Sequence[Job], *, wake: asyncio.Event | None = None
    ) -> None:
        names = [job.name for job in jobs]
        if not names or len(set(names)) != len(names):
            raise ValueError("a schedule needs jobs with distinct names")
        self._reporter = reporter
        self._jobs = list(jobs)
        self._wake = wake
        self._due = dict.fromkeys(names, reporter.clock())

    def due_in(self, name: str, seconds: float) -> None:
        """Run the job ``name`` next ``seconds`` from now, instead of when it would be due."""
        self._due[name] = self._reporter.clock() + seconds

    async def run(self) -> None:
        """Run whatever is due, then wait for the next job or a wake-up, for ever."""
        while True:
            await self.round()
            delay = max(0.0, min(self._due.values()) - self._reporter.clock())
            if self._wake is None:
                await self._reporter.sleep(delay)
            else:
                await wait_or_wake(self._reporter, self._wake, delay)

    async def round(self) -> None:
        """Run every job that is due, or woken, once."""
        if self._wake is not None and self._wake.is_set():
            # Cleared before the jobs run, so a wake-up while they do runs them again.
            self._wake.clear()
            for job in self._jobs:
                if job.on_wake:
                    self._due[job.name] = min(self._due[job.name], self._reporter.clock())
        ok, ran = True, False
        for job in self._jobs:
            started = self._reporter.clock()
            if started < self._due[job.name]:
                continue
            ran = True
            self._due[job.name] = started + job.every
            ok = await self._attempt(job) and ok
        if ran and ok:
            self._reporter.succeeded()

    async def _attempt(self, job: Job) -> bool:
        """Run a job, reporting a failure rather than raising it."""
        try:
            return await job.run() is not False
        except Exception as error:
            # A timeout's message is empty, so its type names it.
            message = str(error) or type(error).__name__
            if len(self._jobs) > 1:
                message = f"{job.name}: {message}"
            self._reporter.problem(message)
            logger.warning("%s: %s", self._reporter.name, message)
            logger.debug("%s: %s", self._reporter.name, job.name, exc_info=error)
            return False


async def wait_or_wake(reporter: Reporter, woken: asyncio.Event, seconds: float) -> None:
    """Wait ``seconds`` on the reporter's sleep, or until ``woken`` is set, such as by an upload."""
    timer = asyncio.ensure_future(reporter.sleep(seconds))
    wake = asyncio.ensure_future(woken.wait())
    done, pending = await asyncio.wait({timer, wake}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    for task in done:
        task.result()


class TickLoop:
    """Calls ``tick`` every ``interval_seconds`` between :meth:`start` and :meth:`stop`.

    A :class:`Schedule` with one job. A tick that raises is logged with its traceback and the
    loop carries on: a loop that died on one bad tick would stop every later piece of work
    without saying so. ``enabled=False`` makes :meth:`start` do nothing, which is how tests drive
    ``tick`` themselves.
    """

    def __init__(
        self,
        tick: Callable[[], Awaitable[None]],
        interval_seconds: float,
        *,
        enabled: bool = True,
        name: str = "scheduler",
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._tick = tick
        self._interval = interval_seconds
        self._enabled = enabled
        self._name = name
        self._clock = clock
        self._sleep = sleep
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        """Whether the loop has been started and not stopped."""
        return self._task is not None

    def start(self) -> None:
        """Begin ticking, unless disabled or already started."""
        if not self._enabled:
            logger.info("%s disabled by configuration", self._name)
            return
        if self._task is not None:
            return
        reporter = LoggingReporter(self._name, clock=self._clock, sleep=self._sleep)
        schedule = Schedule(reporter, [Job(self._name, self._interval, self._run)])
        self._task = asyncio.create_task(schedule.run(), name=self._name)
        logger.info("%s started, ticking every %gs", self._name, self._interval)

    async def stop(self) -> None:
        """Stop ticking and wait for the loop to unwind."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> bool:
        """One tick, its failure logged with the traceback rather than raised."""
        try:
            await self._tick()
        except Exception:
            logger.exception("%s tick failed; the next one tries again", self._name)
            return False
        return True


__all__ = ["Job", "LoggingReporter", "Reporter", "Schedule", "TickLoop", "wait_or_wake"]
