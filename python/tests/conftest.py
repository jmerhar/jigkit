"""Shared test setup: jigkit's own plugin, and the sample application on the import path."""

import sys
from pathlib import Path

# Loaded here, the way an application loads it, rather than with -p: a conftest is imported after
# coverage starts, so the plugin's own lines are measured.
pytest_plugins = ["jigkit.testing"]

#: A small application built on jigkit, with its own Alembic project.
SAMPLE_APP = Path(__file__).parent / "sample_app"

sys.path.insert(0, str(SAMPLE_APP))
