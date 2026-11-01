"""Shared test setup: jigkit's own plugin, the sample application, and a stand-in server."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

# Loaded here, the way an application loads it, rather than with -p: a conftest is imported after
# coverage starts, so the plugin's own lines are measured.
pytest_plugins = ["jigkit.testing"]

#: A small application built on jigkit, with its own Alembic project.
SAMPLE_APP = Path(__file__).parent / "sample_app"

sys.path.insert(0, str(SAMPLE_APP))


@pytest.fixture
async def influx() -> AsyncIterator[object]:
    """A stand-in InfluxDB, or any HTTP service, for the length of one test.

    Imported here rather than at the top: importing a module of the plugin package before pytest
    has registered the plugin would stop its assertions being rewritten.
    """
    from jigkit.testing.http import StubServer, serving

    async with serving(StubServer()) as stub:
        yield stub
