"""Shared test setup: jigkit's own plugin."""

# Loaded here, the way an application loads it, rather than with -p: a conftest is imported after
# coverage starts, so the plugin's own lines are measured.
pytest_plugins = ["jigkit.testing"]
